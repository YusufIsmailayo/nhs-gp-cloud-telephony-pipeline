"""
Bronze ingest for NHS GP Cloud Based Telephony.

Scripted equivalent of notebooks/01_bronze.ipynb (generated from the same cells):
verifies every downloaded file against the SHA-256 manifest, extracts caveat text
from the publication-page snapshots, and writes the telephony, registered-patient
and ODS CSVs to Parquet unchanged (all values as text) with lineage columns.
Run after src/pipeline/download_bronze.py.
"""

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import requests
from bs4 import BeautifulSoup

print("Tools loaded OK")

PROJECT_DIR = Path(__file__).resolve().parents[2]

BRONZE_DIR = PROJECT_DIR / "data" / "bronze"
EVIDENCE_DIR = PROJECT_DIR / "evidence"
PAGES_DIR = EVIDENCE_DIR / "publication_pages"
print("Project :", PROJECT_DIR)
print("Bronze  :", BRONZE_DIR)
print("Evidence:", EVIDENCE_DIR)

def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> tuple[Path, pd.DataFrame]:
    paths = sorted(EVIDENCE_DIR.glob("download_manifest_*.txt"))
    rows = pd.concat([pd.read_csv(p, sep="\t", dtype=str) for p in paths], ignore_index=True)
    return paths[-1], rows.drop_duplicates("path", keep="last").reset_index(drop=True)


def verify_manifest(manifest: pd.DataFrame) -> pd.DataFrame:
    results = []
    for row in manifest.itertuples():
        path = PROJECT_DIR / row.path
        status = "ok"
        if not path.exists():
            r = requests.get(row.source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=300)
            r.raise_for_status()
            if hashlib.sha256(r.content).hexdigest() != row.sha256:
                status = "MISMATCH on re-download (source reissued?) - not saved"
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
                status = "re-downloaded, matches"
        elif sha256_of(path) != row.sha256:
            status = "MISMATCH on disk"
        results.append({"path": row.path, "status": status})
    return pd.DataFrame(results)


MANIFEST_PATH, manifest = load_manifest()
check = verify_manifest(manifest)
print(f"Manifests: {len(sorted(EVIDENCE_DIR.glob('download_manifest_*.txt')))} file(s), latest {MANIFEST_PATH.name} - {len(manifest)} files")
print(check["status"].value_counts().to_string())
bad = check[check["status"].str.startswith("MISMATCH")]
assert bad.empty, f"Stop: fingerprints don't match the manifest:\n{bad.to_string()}"

def extract_caveat_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    lines, keep = [], False
    for tag in main.find_all(["h1", "h2", "p", "li"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if tag.name == "h1":
            lines.append(f"# {text}")
        elif tag.name == "h2":
            keep = text in ("Summary", "Key Facts")
            if keep:
                lines.append(f"\n## {text}")
        elif keep and tag.name == "p":
            lines.append(text)
        if text.startswith("Last edited"):
            lines.append(f"\n{text}")
    return "\n".join(lines) + "\n"


def write_caveats(manifest: pd.DataFrame) -> pd.DataFrame:
    pages = manifest[manifest["path"].str.startswith("evidence/publication_pages/")]
    written = []
    for row in pages.itertuples():
        html_path = PROJECT_DIR / row.path
        out = html_path.with_name(html_path.stem.replace("page_", "caveats_") + ".txt")
        header = (f"Source URL : {row.source_url}\n"
                  f"Retrieved  : {row.downloaded_utc}\n"
                  f"HTML SHA256: {row.sha256}\n\n")
        out.write_text(header + extract_caveat_text(html_path.read_text(encoding="utf-8")))
        written.append({"folder": html_path.parent.name, "file": out.name})
    return pd.DataFrame(written)


caveats = write_caveats(manifest)
print(f"Wrote {len(caveats)} caveat files")
print((PAGES_DIR / "2026-08" / caveats.loc[caveats.folder == "2026-08", "file"].iloc[0]).read_text()[:1500])

KINDS = {
    "By Day and Time": "day_time",
    "By Durations": "durations",
    "Calls Answered Metric": "calls_answered",
}


def read_csv_as_text(raw: bytes) -> pa.Table:
    header = raw.split(b"\n", 1)[0].decode("utf-8-sig").strip().split(",")
    return pacsv.read_csv(
        pa.BufferReader(raw),
        read_options=pacsv.ReadOptions(encoding="utf-8"),
        convert_options=pacsv.ConvertOptions(
            column_types={c: pa.string() for c in header},
            strings_can_be_null=False,
        ),
    )


def count_data_lines(raw: bytes) -> int:
    return raw.count(b"\n") - 1 + (0 if raw.endswith(b"\n") else 1)


def with_lineage(table: pa.Table, **lineage: str) -> pa.Table:
    for name, value in lineage.items():
        table = table.append_column(name, pa.array([value] * table.num_rows, pa.string()).dictionary_encode())
    return table


def zip_to_parquet(zip_path: Path, out_path: Path, month: str, sha: str) -> dict:
    tables, raw_rows = [], 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in sorted(zf.namelist()):
            raw = zf.read(member)
            raw_rows += count_data_lines(raw)
            tables.append(with_lineage(
                read_csv_as_text(raw),
                _publication_month=month,
                _source_file=zip_path.name,
                _source_member=member,
                _source_sha256=sha,
            ))
    table = pa.concat_tables(tables)
    assert table.num_rows == raw_rows, f"{zip_path.name}: {table.num_rows:,} rows written vs {raw_rows:,} in CSV"
    pq.write_table(table, out_path, compression="zstd")
    return {
        "bronze_file": str(out_path.relative_to(PROJECT_DIR)),
        "rows": table.num_rows,
        "source_columns": "|".join(c for c in table.column_names if not c.startswith("_")),
        "source_file": str(zip_path.relative_to(PROJECT_DIR)),
        "source_sha256": sha,
        "members": len(tables),
    }


sha_by_path = dict(zip(manifest["path"], manifest["sha256"]))
inventory = []
for month_dir in sorted((BRONZE_DIR / "telephony").iterdir()):
    for zip_path in sorted(month_dir.glob("*.zip")):
        kind = next(v for k, v in KINDS.items() if k in zip_path.name)
        sha = sha_by_path[str(zip_path.relative_to(PROJECT_DIR))]
        inventory.append(zip_to_parquet(zip_path, month_dir / f"{kind}.parquet", month_dir.name, sha))
        print(f"{month_dir.name}  {kind:<15} {inventory[-1]['rows']:>10,} rows")

inv = pd.DataFrame(inventory)
inv["kind"] = inv["bronze_file"].str.extract(r"/([a-z_]+)\.parquet$")
inv["month"] = inv["bronze_file"].str.extract(r"/(\d{4}-\d{2})/")
schemas = (inv.groupby(["kind", "source_columns"])["month"]
              .agg(lambda m: f"{m.min()} to {m.max()} ({len(m)} months)")
              .reset_index())
pd.set_option("display.max_colwidth", None)
print(schemas.to_string())

for zip_path in sorted((BRONZE_DIR / "registered_patients").rglob("*.zip")):
    sha = sha_by_path[str(zip_path.relative_to(PROJECT_DIR))]
    out = zip_path.with_suffix(".parquet")
    inventory.append(zip_to_parquet(zip_path, out, zip_path.parent.name, sha))
    print(f"{zip_path.name:<28} {inventory[-1]['rows']:>8,} rows")

for csv_path in sorted((BRONZE_DIR / "ods").rglob("epraccur.csv")):
    raw = csv_path.read_bytes()
    n_cols = len(next(iter(pacsv.open_csv(pa.BufferReader(raw),
                 read_options=pacsv.ReadOptions(autogenerate_column_names=True)))).schema)
    names = [f"col_{i:02d}" for i in range(1, n_cols + 1)]
    table = pacsv.read_csv(
        pa.BufferReader(raw),
        read_options=pacsv.ReadOptions(column_names=names),
        convert_options=pacsv.ConvertOptions(column_types={c: pa.string() for c in names},
                                             strings_can_be_null=False),
    )
    assert table.num_rows == count_data_lines(raw) + 1, "epraccur row count mismatch"
    sha = sha_by_path[str(csv_path.relative_to(PROJECT_DIR))]
    table = with_lineage(table, _snapshot=csv_path.parent.name.replace("epraccur_", ""),
                         _source_file=csv_path.name, _source_sha256=sha)
    out = csv_path.with_suffix(".parquet")
    pq.write_table(table, out, compression="zstd")
    inventory.append({"bronze_file": str(out.relative_to(PROJECT_DIR)), "rows": table.num_rows,
                      "source_columns": "|".join(names), "source_file": str(csv_path.relative_to(PROJECT_DIR)),
                      "source_sha256": sha, "members": 1})
    print(f"{csv_path.parent.name:<28} {table.num_rows:>8,} rows x {n_cols} cols")

for csv_path in sorted((BRONZE_DIR / "fingertips").rglob("*.csv")):
    raw = csv_path.read_bytes()
    sha = sha_by_path[str(csv_path.relative_to(PROJECT_DIR))]
    table = read_csv_as_text(raw)
    assert table.num_rows == count_data_lines(raw), f"{csv_path.name}: row count mismatch"
    table = with_lineage(table, _snapshot=csv_path.parent.name.rsplit("_", 1)[-1],
                         _source_file=csv_path.name, _source_sha256=sha)
    out = csv_path.with_suffix(".parquet")
    pq.write_table(table, out, compression="zstd")
    inventory.append({"bronze_file": str(out.relative_to(PROJECT_DIR)), "rows": table.num_rows,
                      "source_columns": "|".join(c for c in table.column_names if not c.startswith("_")),
                      "source_file": str(csv_path.relative_to(PROJECT_DIR)), "source_sha256": sha, "members": 1})
    print(f"{csv_path.parent.name:<28} {table.num_rows:>8,} rows")

inventory_df = pd.DataFrame(inventory)
inventory_df.insert(0, "built_utc", datetime.now(timezone.utc).isoformat(timespec="seconds"))
inventory_df.insert(1, "manifest", MANIFEST_PATH.name)
inventory_path = EVIDENCE_DIR / "bronze_inventory.csv"
inventory_df.to_csv(inventory_path, index=False)

print(f"{len(inventory_df)} Bronze files, {inventory_df['rows'].sum():,} rows -> {inventory_path.relative_to(PROJECT_DIR)}")
print(inventory_df[["bronze_file", "rows", "members"]].to_string())
