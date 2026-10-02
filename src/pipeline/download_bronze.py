"""Bronze download: telephony publications, registered patients, ODS epraccur, Fingertips IMD.

Writes raw files to data/bronze/, dated page snapshots to evidence/publication_pages/,
and a SHA-256 manifest to evidence/download_manifest_<date>.txt.

Run from anywhere:
    python src/pipeline/download_bronze.py                # every source; rewrites today's manifest
    python src/pipeline/download_bronze.py fingertips     # named sources only; appends to today's manifest
Sources: telephony, support, registered, ods, fingertips.
"""
import hashlib, re, sys, urllib.parse, datetime as dt, pathlib, requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
TODAY = dt.date.today().isoformat()
UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://digital.nhs.uk/data-and-information/publications/statistical/cloud-based-telephony-data-in-general-practice"
REG = "https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/august-2026"
FINGERTIPS = "https://fingertips.phe.org.uk/api"
MONTHS = ["january","february","march","april","may","june","july","august","september","october","november","december"]
manifest = []


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def save(url, dest):
    r = requests.get(url, headers=UA, timeout=300)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    manifest.append((hashlib.sha256(r.content).hexdigest(), dest.stat().st_size, str(dest.relative_to(ROOT)), url, now()))
    print(f"{dest.stat().st_size:>12,}  {dest.relative_to(ROOT)}")
    return r.content


def snapshot(url, folder):
    html = save(url, ROOT / "evidence/publication_pages" / folder / f"page_{TODAY}.html")
    return html.decode("utf-8", "replace")


def resources(html):
    return sorted(set(re.findall(r'href="(https://files\.digital\.nhs\.uk/[^"]+)"', html)))


def fname(url):
    return urllib.parse.unquote(url.rsplit("/", 1)[1])


def telephony():
    """August 2026 plus every earlier published month on the series index."""
    index = requests.get(BASE, headers=UA, timeout=60).text
    slugs = sorted(set(re.findall(r'cloud-based-telephony-data-in-general-practice/([a-z]+-\d{4})"', index)))
    for slug in slugs:
        m, y = slug.split("-")
        ym = f"{y}-{MONTHS.index(m) + 1:02d}"
        if ym > "2026-08":
            print(f"skip {slug}: upcoming, not yet published")
            continue
        html = snapshot(f"{BASE}/{slug}", ym)
        for u in resources(html):
            save(u, ROOT / "data/bronze/telephony" / ym / fname(u))


def support():
    snapshot(f"{BASE}/support-information", "support-information")


def registered():
    """Registered patients: practice totals + mapping only."""
    html = snapshot(REG, "registered_patients_2026-08")
    for u in resources(html):
        if fname(u) in ("gp-reg-pat-prac-all.zip", "gp-reg-pat-prac-map.zip"):
            save(u, ROOT / "data/bronze/registered_patients/2026-08" / fname(u))


def ods():
    save("https://www.odsdatasearchandexport.nhs.uk/api/getReport?report=epraccur",
         ROOT / f"data/bronze/ods/epraccur_{TODAY}/epraccur.csv")


def fingertips():
    """Practice deprivation score (IMD 2025), Fingertips indicator 94240, all GP practices.

    The indicator metadata gives only the name and source, so the metadata response is
    kept as evidence alongside the data.
    """
    folder = ROOT / f"data/bronze/fingertips/imd2025_gp_{TODAY}"
    save(f"{FINGERTIPS}/all_data/csv/by_indicator_id?indicator_ids=94240&child_area_type_id=7",
         folder / "indicator_94240_gp.csv")
    save(f"{FINGERTIPS}/indicator_metadata/by_indicator_id?indicator_ids=94240",
         ROOT / f"evidence/reference/fingertips_94240_metadata_{TODAY}.json")
    # NHS England's description of practice-level IMD (patient-LSOA weighted), the closest
    # published statement of the method; Fingertips doesn't document it for 94240
    save("https://digital.nhs.uk/supplementary-information/2025/diagnostic-prevalence-of-autism-by-general-practice-level-deprivation",
         ROOT / f"evidence/reference/nhse_practice_imd_method_{TODAY}.html")


SOURCES = {"telephony": telephony, "support": support, "registered": registered, "ods": ods, "fingertips": fingertips}

if __name__ == "__main__":
    chosen = sys.argv[1:] or list(SOURCES)
    unknown = [c for c in chosen if c not in SOURCES]
    assert not unknown, f"unknown source(s) {unknown}; choose from {list(SOURCES)}"
    for name in chosen:
        SOURCES[name]()

    out = ROOT / f"evidence/download_manifest_{TODAY}.txt"
    append = bool(sys.argv[1:]) and out.exists()
    with out.open("a" if append else "w") as f:
        if not append:
            f.write("sha256\tbytes\tpath\tsource_url\tdownloaded_utc\n")
        for row in manifest:
            f.write("\t".join(map(str, row)) + "\n")
    print(f"{len(manifest)} files -> {out.relative_to(ROOT)} ({'appended' if append else 'written'})")
