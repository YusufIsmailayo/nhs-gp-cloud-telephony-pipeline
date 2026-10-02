"""Bronze download: telephony publications, registered patients, ODS epraccur.

Writes raw files to data/bronze/, dated page snapshots to evidence/publication_pages/,
and a SHA-256 manifest to evidence/download_manifest_<date>.txt.
Run from anywhere: python src/pipeline/download_bronze.py
"""
import hashlib, re, urllib.parse, datetime as dt, pathlib, requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
TODAY = dt.date.today().isoformat()
UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://digital.nhs.uk/data-and-information/publications/statistical/cloud-based-telephony-data-in-general-practice"
REG = "https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/august-2026"
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


# 1-2. Telephony: August 2026 plus every earlier published month on the series index
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

# 3. Supporting Information
snapshot(f"{BASE}/support-information", "support-information")

# 4. Registered patients: practice totals + mapping only
html = snapshot(REG, "registered_patients_2026-08")
for u in resources(html):
    if fname(u) in ("gp-reg-pat-prac-all.zip", "gp-reg-pat-prac-map.zip"):
        save(u, ROOT / "data/bronze/registered_patients/2026-08" / fname(u))

# 5. ODS epraccur
save("https://www.odsdatasearchandexport.nhs.uk/api/getReport?report=epraccur",
     ROOT / f"data/bronze/ods/epraccur_{TODAY}/epraccur.csv")

out = ROOT / f"evidence/download_manifest_{TODAY}.txt"
with out.open("w") as f:
    f.write("sha256\tbytes\tpath\tsource_url\tdownloaded_utc\n")
    for row in manifest:
        f.write("\t".join(map(str, row)) + "\n")
print(f"{len(manifest)} files -> {out.relative_to(ROOT)}")
