"""
Silver build for NHS GP Cloud Based Telephony.

Scripted equivalent of notebooks/02_silver.ipynb (generated from the same cells):
types the call files, applies the Unassigned/shared-account rule, builds the
practice dimension from the participation lists, names the epraccur columns from
the ODS specification, and parses the published Table 1/Table 2 for Gold's
reconciliation gate. Run after src/pipeline/bronze_ingest.py.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[2]

BRONZE_DIR = PROJECT_DIR / "data" / "bronze"
SILVER_DIR = PROJECT_DIR / "data" / "silver"
EVIDENCE_DIR = PROJECT_DIR / "evidence"
SILVER_DIR.mkdir(parents=True, exist_ok=True)

MONTHS = sorted(p.name for p in (BRONZE_DIR / "telephony").iterdir() if p.is_dir())
ANALYSIS_MONTH = "2026-08"
pd.set_option("display.max_colwidth", 80)
print("Months in Bronze:", ", ".join(MONTHS))

INDICATORS = pd.DataFrame([
    ("CBT001", "inbound", "All external inbound calls"),
    ("CBT002", "ended_in_ivr", "Ended during the IVR (automated routing) stage"),
    ("CBT003", "answered_by_wait", "Answered by practice staff, by wait-time bucket"),
    ("CBT004", "missed", "Ended unanswered while queuing or ringing; includes voicemail"),
    ("CBT005", "callback_requested", "Virtual-queue callback requested"),
    ("CBT006", "callback_made", "Automatic callback made"),
    ("CBT007", "answered_by_duration", "Answered by practice staff, by call-duration bucket"),
], columns=["indicator", "indicator_name", "definition"])
INDICATOR_NAME = dict(zip(INDICATORS.indicator, INDICATORS.indicator_name))
INDICATORS.to_csv(SILVER_DIR / "indicators.csv", index=False)
print((INDICATORS).to_string())

checks = []
for month in MONTHS:
    b = pd.read_parquet(BRONZE_DIR / "telephony" / month / "day_time.parquet",
                        columns=["REGION_CODE", "PRACTICE_CODE"])
    unassigned, unmapped = b.PRACTICE_CODE.eq("Unassigned"), b.REGION_CODE.eq("Unmapped")
    checks.append({"month": month,
                   "unassigned_rows": int(unassigned.sum()),
                   "of_which_region_unmapped": int((unassigned & unmapped).sum()),
                   "unmapped_but_not_unassigned": int((unmapped & ~unassigned).sum())})
checks = pd.DataFrame(checks)
assert (checks.unmapped_but_not_unassigned == 0).all(), "an Unmapped row is attributed to a practice"

b = pd.read_parquet(BRONZE_DIR / "telephony" / ANALYSIS_MONTH / "day_time.parquet")
u = b[b.PRACTICE_CODE.eq("Unassigned") & b.Indicator.eq("CBT001")]
u_calls = u.Value.astype(float)
depth = pd.DataFrame({
    "level": ["region", "ICB", "sub-ICB", "PCN"],
    "share_of_shared_account_calls_placed": [
        round(u_calls[u[c].ne("Unmapped")].sum() / u_calls.sum(), 3)
        for c in ["REGION_CODE", "ICB_CODE", "SUB_ICB_LOCATION_CODE", "PCN_CODE"]],
})
print(f"{ANALYSIS_MONTH}: shared-account inbound calls = {int(u_calls.sum()):,} "
      f"({u_calls.sum() / b.loc[b.Indicator.eq('CBT001'), 'Value'].astype(float).sum():.1%} of all inbound)")
del b, u
print(checks.to_string())
print((depth).to_string())

KIND_DETAIL = {"day_time": "time_band", "durations": "duration_bucket", "calls_answered": "wait_bucket"}
RENAME = {"Date": "date", "REGION_CODE": "region_code", "ICB_CODE": "icb_code",
          "SUB_ICB_LOCATION_CODE": "sub_icb_code", "PCN_CODE": "pcn_code",
          "PRACTICE_CODE": "practice_code", "Indicator": "indicator",
          "Time_Category": "time_band", "Duration": "duration_bucket",
          "Wait_Time": "wait_bucket", "Core_Category": "core_category"}


def bucket_bounds(bucket: pd.Series) -> pd.DataFrame:
    s = bucket.astype(str)
    lower = pd.Series(np.nan, index=s.index)
    upper = pd.Series(np.nan, index=s.index)
    rng = s.str.extract(r"^(\d+)_(\d+)$").astype(float)
    lower, upper = lower.fillna(rng[0]), upper.fillna(rng[1])
    zero = s.eq("0")
    lower[zero], upper[zero] = 0, 0
    over = s.str.extract(r"^>(\d+)$")[0].astype(float)
    lower = lower.fillna(over + 1)
    unknown = ~(s.eq("TOTAL") | lower.notna())
    assert not unknown.any(), f"Unrecognised buckets: {sorted(s[unknown].unique())}"
    return pd.DataFrame({"lower_s": lower.astype("Int64"), "upper_s": upper.astype("Int64")})


def silver_calls(kind: str, month: str) -> tuple[pd.DataFrame, dict]:
    b = pd.read_parquet(BRONZE_DIR / "telephony" / month / f"{kind}.parquet")
    s = b[[c for c in b.columns if not c.startswith("_")]].rename(columns=RENAME)

    calls = pd.to_numeric(s.pop("Value"), errors="coerce")
    assert calls.notna().all(), f"{kind} {month}: non-numeric Value"
    assert (calls >= 0).all() and (calls == calls.round()).all(), f"{kind} {month}: Value not a whole count"
    s["calls"] = calls.astype("int64")

    s["date"] = pd.to_datetime(s["date"], format="ISO8601")
    assert (s["date"].dt.strftime("%Y-%m") == month).all(), f"{kind} {month}: date outside month"
    s.insert(1, "weekday", s["date"].dt.day_name())

    shared = s["practice_code"].eq("Unassigned")
    cleaned = s["practice_code"].where(shared, s["practice_code"].str.strip().str.upper())
    changed = int((cleaned != s["practice_code"]).sum())
    s["practice_code"] = cleaned
    s["attribution"] = np.where(shared, "shared_account", "practice")
    s["indicator_name"] = s["indicator"].map(INDICATOR_NAME)
    assert s["indicator_name"].notna().all(), f"{kind} {month}: unknown indicator"

    detail = KIND_DETAIL[kind]
    if detail == "time_band":
        s["time_band"] = s["time_band"].str.replace(" ", "", regex=False)
    else:
        s = pd.concat([s, bucket_bounds(s[detail])], axis=1)

    s.insert(0, "month", month)
    for c in s.columns:
        if s[c].dtype == object:
            s[c] = s[c].astype("category")

    out_dir = SILVER_DIR / f"calls_{kind}"
    out_dir.mkdir(exist_ok=True)
    s.to_parquet(out_dir / f"{month}.parquet", index=False)
    return s, {"kind": kind, "month": month, "bronze_rows": len(b), "silver_rows": len(s),
               "value_sum_all_indicators": int(s["calls"].sum()), "practice_codes_changed_by_trim": changed}


log, national = [], []
for month in MONTHS:
    for kind in KIND_DETAIL:
        if not (BRONZE_DIR / "telephony" / month / f"{kind}.parquet").exists():
            continue
        s, entry = silver_calls(kind, month)
        log.append(entry)
        national.append(s.groupby(["month", "indicator"], observed=True)["calls"].sum()
                         .rename(kind).reset_index())
        del s

silver_log = pd.DataFrame(log)
assert (silver_log.bronze_rows == silver_log.silver_rows).all(), "rows lost between Bronze and Silver"
print("Practice codes changed by trim/upper-case:", silver_log.practice_codes_changed_by_trim.sum())
print((silver_log).to_string())

by_kind = [pd.concat([f for f in national if kind in f.columns], ignore_index=True) for kind in KIND_DETAIL]
nat = by_kind[0]
for frame in by_kind[1:]:
    nat = nat.merge(frame, on=["month", "indicator"], how="outer")
present = nat[list(KIND_DETAIL)]
nat["max_diff"] = (present.max(axis=1) - present.min(axis=1)).where(present.notna().sum(axis=1) > 1)
nat["indicator_name"] = nat["indicator"].map(INDICATOR_NAME)
nat.to_csv(SILVER_DIR / "national_by_indicator_and_file.csv", index=False)
print("Indicator/month pairs where files disagree:", int((nat.max_diff > 0).sum()))
print((nat[nat.month == ANALYSIS_MONTH]).to_string())

PARTICIPATION_COLS = ["month_published", "practice_code", "practice_name", "pcn_code", "pcn_name",
                      "sub_icb_code", "sub_icb_name", "icb_code", "icb_name", "region_code",
                      "region_name", "agreed", "included", "shared_account", "account_practice_codes"]
EXPECTED_HEADINGS = ["Month", "GP Code", "GP Name", "PCN Code", "PCN Name", "Sub ICB Code",
                     "Sub ICB Name", "ICB Code", "ICB Name", "Region Code", "Region Name",
                     "Agreed to Participate", "Data received / Passed", "Practice Code has been un",
                     "List of open and act"]  # Oct 2025 heading reads "actice"
ODS_PRACTICE = re.compile(r"^[A-Z]\d{5}$")
HEADING_GAPS = []


def read_participation(month: str) -> pd.DataFrame:
    path = next((BRONZE_DIR / "telephony" / month).glob("CBT-participation*.xlsx"))
    raw = pd.read_excel(path, sheet_name="Table 1", header=None, dtype=str)
    hdr = raw.index[raw[0].astype(str).str.strip().eq("Month")][0]
    headings = raw.iloc[hdr, :15].astype(str).tolist()
    for got, want in zip(headings, EXPECTED_HEADINGS):
        if got == "nan":  # Nov 2025 leaves the "included" heading blank; the Yes/No check below still applies
            HEADING_GAPS.append((month, want))
            continue
        assert want.lower() in got.lower(), f"{month}: heading {got!r} - expected {want!r}"
    body = raw.iloc[hdr + 1:, :15].copy()
    body.columns = PARTICIPATION_COLS
    body = body[body.practice_code.notna()]
    body["practice_code"] = body.practice_code.str.strip().str.upper()
    odd = body[~body.practice_code.str.match(ODS_PRACTICE)]
    assert odd.empty, f"{month}: non-ODS codes {odd.practice_code.tolist()[:5]}"
    for flag in ["agreed", "included", "shared_account"]:
        assert body[flag].isin(["Yes", "No"]).all(), f"{month}: {flag} not Yes/No"
        body[flag] = body[flag].eq("Yes")
    body["account_practice_codes"] = body.account_practice_codes.fillna("")
    body["account_size"] = body.account_practice_codes.str.split(",").map(lambda x: len([c for c in x if c]))
    body.insert(0, "month", month)
    return body.drop(columns="month_published")


participation = pd.concat([read_participation(m) for m in MONTHS], ignore_index=True)
assert not participation.duplicated(["month", "practice_code"]).any()
print("Blank headings accepted (column checked by content instead):", HEADING_GAPS)

summary = participation.groupby("month").agg(
    open_active=("practice_code", "size"),
    agreed=("agreed", "sum"),
    included=("included", "sum"),
    included_shared_account=("shared_account", lambda s: int((s & participation.loc[s.index, "included"]).sum())),
)
print((summary).to_string())

def csv_practices(month: str) -> set:
    s = pd.read_parquet(SILVER_DIR / "calls_day_time" / f"{month}.parquet", columns=["practice_code", "attribution"])
    return set(s.loc[s.attribution.eq("practice"), "practice_code"].astype(str))


rows = []
for month in MONTHS:
    p = participation[participation.month == month]
    in_csv = csv_practices(month)
    own = set(p.loc[p.included & ~p.shared_account, "practice_code"])
    shared = set(p.loc[p.included & p.shared_account, "practice_code"])
    rows.append({
        "month": month,
        "included_own_account": len(own),
        "included_shared_account": len(shared),
        "csv_practice_codes": len(in_csv),
        "own_account_missing_from_csv": len(own - in_csv),
        "shared_but_published_individually": len(shared & in_csv),
        "csv_codes_not_included": len(in_csv - own - shared),
    })
    participation.loc[participation.month == month, "has_own_call_rows"] = \
        participation.loc[participation.month == month, "practice_code"].isin(in_csv)

practice_match = pd.DataFrame(rows)
print((practice_match).to_string())

participation["has_own_call_rows"] = participation.has_own_call_rows.astype(bool)
participation["shared_but_published_individually"] = participation.shared_account & participation.has_own_call_rows
participation["attribution"] = np.select(
    [~participation.included,
     participation.has_own_call_rows,
     participation.shared_account],
    ["not_included", "practice", "shared_account"],
    default="included_but_no_rows",
)
print(participation[participation.month == ANALYSIS_MONTH].attribution.value_counts().to_string())
participation.to_parquet(SILVER_DIR / "practice_participation.parquet", index=False)

EPRACCUR_COLS = [
    "practice_code", "name", "nhser_code", "icb_code", "address_1", "address_2", "address_3",
    "town", "county", "postcode", "open_date", "close_date", "status", "org_sub_type",
    "commissioner_sub_icb", "join_provider_date", "left_provider_date", "telephone",
    "null_19", "null_20", "null_21", "amended_record_indicator", "null_23",
    "provider_purchaser", "null_25", "role_code", "null_27",
]
e = pd.read_parquet(next((BRONZE_DIR / "ods").glob("epraccur_*/epraccur.parquet")))
snapshot = e["_snapshot"].iloc[0]
e = e[[f"col_{i:02d}" for i in range(1, 28)]]
e.columns = EPRACCUR_COLS
null_cols = [c for c in EPRACCUR_COLS if c.startswith("null_")]
assert (e[null_cols] == "").all().all(), "a column the spec says is NULL has data"
register = e.drop(columns=null_cols + ["county", "amended_record_indicator"])
for c in ["open_date", "close_date", "join_provider_date", "left_provider_date"]:
    register[c] = pd.to_datetime(register[c].replace("", None), format="%Y%m%d")
register["is_gp_practice"] = register.role_code.str.split("|").map(lambda r: "RO76" in r)
register["snapshot_date"] = pd.Timestamp(snapshot)
register.to_parquet(SILVER_DIR / "practice_register.parquet", index=False)

gp = register[register.is_gp_practice]
print(f"epraccur {snapshot}: {len(register):,} prescribing cost centres, {len(gp):,} GP practices (RO76)")
print(gp.status.value_counts().to_string())

reg_dir = BRONZE_DIR / "registered_patients" / ANALYSIS_MONTH
totals = pd.read_parquet(reg_dir / "gp-reg-pat-prac-all.parquet")
mapping = pd.read_parquet(reg_dir / "gp-reg-pat-prac-map.parquet")
assert totals.CODE.is_unique and mapping.PRACTICE_CODE.is_unique
assert (totals.SEX == "ALL").all() and (totals.AGE == "ALL").all()
assert set(totals.CODE) == set(mapping.PRACTICE_CODE), "totals and mapping cover different practices"
registered = (totals[["CODE", "EXTRACT_DATE", "NUMBER_OF_PATIENTS"]]
              .rename(columns={"CODE": "practice_code", "EXTRACT_DATE": "extract_date",
                               "NUMBER_OF_PATIENTS": "registered_patients"})
              .merge(mapping.drop(columns=["PUBLICATION", "EXTRACT_DATE"])
                            .rename(columns=str.lower), on="practice_code", how="inner"))
registered["registered_patients"] = registered.registered_patients.astype("int64")
registered["extract_date"] = pd.to_datetime(registered.extract_date)
registered = registered.rename(columns={"supplier_name": "clinical_system_supplier"})
registered.to_parquet(SILVER_DIR / "registered_patients.parquet", index=False)
print(f"Registered patients {registered.extract_date.iloc[0]:%d %b %Y}: {len(registered):,} practices, "
      f"{registered.registered_patients.sum():,} patients")

aug = participation[participation.month == ANALYSIS_MONTH]
P = set(aug.practice_code)
R = set(registered.practice_code)
G_active = set(gp.loc[gp.status.eq("ACTIVE") & gp.nhser_code.str.startswith("Y"), "practice_code"])

join_report = pd.DataFrame([
    ("participation list (open & active, Aug 2026)", len(P), ""),
    ("  ...not in registered-patients file", len(P - R), ", ".join(sorted(P - R)[:6]) + (" ..." if len(P - R) > 6 else "")),
    ("  ...not ACTIVE GP practice in epraccur (2 Oct)", len(P - G_active), ", ".join(sorted(P - G_active))),
    ("registered-patients file", len(R), ""),
    ("  ...not in participation list", len(R - P), ", ".join(sorted(R - P))),
    ("ACTIVE GP practices in England, epraccur (2 Oct)", len(G_active), ""),
    ("  ...not in participation list", len(G_active - P), ", ".join(sorted(G_active - P))),
], columns=["set", "count", "codes"])
print("epraccur status of the participation practices it doesn't list as active:",
      gp[gp.practice_code.isin(P - G_active)].status.value_counts().to_dict())
print((join_report).to_string())

practice_dim = (aug.drop(columns=["month"])
                .merge(registered[["practice_code", "registered_patients", "clinical_system_supplier",
                                   "comm_region_code", "icb_code"]]
                       .rename(columns={"icb_code": "icb_code_registered", "comm_region_code": "region_code_registered"}),
                       on="practice_code", how="left", indicator="in_registered")
                .merge(register[["practice_code", "status", "postcode", "open_date", "close_date"]]
                       .rename(columns={"status": "ods_status", "postcode": "ods_postcode"}),
                       on="practice_code", how="left"))
practice_dim["in_registered"] = practice_dim.in_registered.eq("both")
practice_dim.insert(0, "month", ANALYSIS_MONTH)
geo_mismatch = practice_dim.in_registered & (practice_dim.icb_code != practice_dim.icb_code_registered)
print("ICB differs between participation list and registered-patients mapping:", int(geo_mismatch.sum()))
practice_dim.to_parquet(SILVER_DIR / f"practice_dim_{ANALYSIS_MONTH}.parquet", index=False)
join_report.to_csv(EVIDENCE_DIR / f"silver_practice_join_{ANALYSIS_MONTH}.csv", index=False)
print((practice_dim.attribution.value_counts()).to_string())

def outcome_check(month: str) -> pd.DataFrame:
    d = pd.read_parquet(SILVER_DIR / "calls_durations" / f"{month}.parquet",
                        columns=["practice_code", "attribution", "indicator", "calls"])
    d = d[d.attribution.eq("practice")]
    w = d.groupby(["practice_code", "indicator"], observed=True)["calls"].sum().unstack(fill_value=0)
    w = w.reindex(columns=INDICATORS.indicator, fill_value=0)
    w["outcomes"] = w[["CBT002", "CBT003", "CBT004", "CBT005"]].sum(axis=1)
    w["gap"] = w["outcomes"] - w["CBT001"]
    w["month"] = month
    return w.reset_index()


oc = pd.concat([outcome_check(m) for m in MONTHS], ignore_index=True)
tol = 0.01
oc_summary = oc.groupby("month").apply(lambda t: pd.Series({
    "practices": len(t),
    "exact_match": int((t.gap == 0).sum()),
    "outcomes_over_inbound_by_>1%": int((t.gap > tol * t.CBT001).sum()),
    "outcomes_under_inbound_by_>1%": int((t.gap < -tol * t.CBT001).sum()),
    "net_gap_calls": int(t.gap.sum()),
    "gross_gap_calls": int(t.gap.abs().sum()),
    "cbt003_ne_cbt007": int((t.CBT003 != t.CBT007).sum()),
}), include_groups=False)
oc.to_parquet(SILVER_DIR / "practice_outcome_check.parquet", index=False)
print((oc_summary).to_string())

def summary_path(month: str) -> Path:
    return next((BRONZE_DIR / "telephony" / month).glob("*Publication Summary*.xlsx"))


def parse_table1(month: str) -> pd.DataFrame:
    raw = pd.read_excel(summary_path(month), sheet_name="Table 1", header=None)
    is_date = raw.map(lambda v: isinstance(v, pd.Timestamp) or hasattr(v, "year"))
    date_row = is_date.sum(axis=1).idxmax()
    date_cols = [c for c in raw.columns if is_date.loc[date_row, c]]
    first = date_cols[0]
    out, group = [], None
    for i in range(date_row + 1, len(raw)):
        row = raw.iloc[i]
        labels = [str(v).strip() for v in row[:first] if pd.notna(v) and str(v).strip()]
        values = pd.to_numeric(row[date_cols], errors="coerce")
        if str(row.iloc[0]).startswith("Notes"):
            break
        if not labels or values.isna().all():
            continue
        if len(labels) == 2:
            group = labels[0]
        for col, v in zip(date_cols, values):
            out.append({"publication_month": month,
                        "reference_month": pd.Timestamp(raw.loc[date_row, col]).strftime("%Y-%m"),
                        "group": group, "measure": labels[-1], "value": v})
    return pd.DataFrame(out)


def parse_table2(month: str) -> pd.DataFrame:
    raw = pd.read_excel(summary_path(month), sheet_name="Table 2", header=None)
    hdr = raw.index[raw.apply(lambda r: r.astype(str).str.contains("Total Count of Inbound").any(), axis=1)][0]
    heads = raw.iloc[hdr].tolist()
    total_col = heads.index(next(h for h in heads if isinstance(h, str) and "Total Count" in h))
    band_cols = [c for c in range(total_col + 1, len(heads)) if isinstance(heads[c], str)]
    rows = []
    for i in range(hdr + 1, len(raw)):
        date = raw.iloc[i, total_col - 1]
        if not hasattr(date, "year"):
            if rows:
                break
            continue
        for c in band_cols:
            rows.append({"publication_month": month, "date": pd.Timestamp(date),
                         "time_band": heads[c].replace(" ", ""), "calls": raw.iloc[i, c]})
        rows.append({"publication_month": month, "date": pd.Timestamp(date),
                     "time_band": "TOTAL", "calls": raw.iloc[i, total_col]})
    return pd.DataFrame(rows)


table1 = pd.concat([parse_table1(m) for m in MONTHS], ignore_index=True)
table2 = pd.concat([parse_table2(m) for m in MONTHS], ignore_index=True)
table2["calls"] = table2.calls.astype("int64")
table2["weekday"] = table2.date.dt.day_name()
print(f"Table 1: {len(table1):,} values, {table1.measure.nunique()} measures, from {table1.publication_month.nunique()} workbooks")
print(f"Table 2: {table2.date.nunique()} dates")
print((table1[(table1.publication_month == ANALYSIS_MONTH) & (table1.reference_month == ANALYSIS_MONTH)][["group", "measure", "value"]]).to_string())

revisions = (table1.dropna(subset=["value"])
             .groupby(["reference_month", "group", "measure"])["value"]
             .agg(editions="size", distinct=lambda v: v.round(6).nunique(), first="first", last="last")
             .reset_index())
assert revisions.editions.max() <= len(MONTHS), "a value appears more often than there are workbooks"
revised = revisions[(revisions.editions > 1) & (revisions.distinct > 1)].copy()
revised["change_pct"] = ((revised["last"] - revised["first"]) / revised["first"] * 100).round(2)
print(f"{len(revised)} of {int((revisions.editions > 1).sum())} republished values changed between editions")
revised.to_csv(EVIDENCE_DIR / "silver_table1_revisions.csv", index=False)
print(((revised.groupby(["group", "measure"])
        .agg(months_revised=("reference_month", "size"),
             earliest=("reference_month", "min"), latest=("reference_month", "max"),
             largest_change_pct=("change_pct", lambda c: c.loc[c.abs().idxmax()]))
        .sort_values("months_revised", ascending=False))).to_string())

BAND_FROM_LABEL = [("1 minute or less", "le_1min"), ("1 to 2", "1_2min"), ("2 to 5", "2_5min"), ("over 5", "over_5min")]
BAND_SECONDS = {"le_1min": (0, 60), "1_2min": (61, 120), "2_5min": (121, 300), "over_5min": (301, None)}


def band_of(label: str) -> str:
    return next(b for text, b in BAND_FROM_LABEL if text in label)


def duration_check(month: str) -> pd.DataFrame:
    d = pd.read_parquet(SILVER_DIR / "calls_durations" / f"{month}.parquet")
    d = d[d.indicator.eq("CBT007")]
    rebuilt = pd.Series({b: int(d.loc[(d.lower_s >= lo) & ((d.upper_s <= hi) if hi else d.upper_s.isna()), "calls"].sum())
                         for b, (lo, hi) in BAND_SECONDS.items()})
    share = (rebuilt / rebuilt.sum()).round(3)
    t = table1[(table1.publication_month == month) & (table1.reference_month == month)
               & table1.measure.str.contains("uration")].copy()
    t["band"] = t.measure.map(band_of)
    t["kind"] = np.where(t.measure.str.startswith("Percentage"), "share", "count")
    t["rebuilt"] = np.where(t.kind == "count", t.band.map(rebuilt), t.band.map(share))
    t["matches_label"] = (t.value - t.rebuilt).abs() <= np.where(t.kind == "count", 0, 0.0011)
    # which band's rebuilt share does the published % actually equal?
    t["value_actually_is"] = [
        next((b for b in share.index if abs(share[b] - v) <= 0.0011), "no match") if k == "share" else b0
        for v, k, b0 in zip(t.value, t.kind, t.band)]
    return t[["publication_month", "kind", "measure", "band", "value", "rebuilt", "matches_label", "value_actually_is"]]


dur = pd.concat([duration_check(m) for m in MONTHS], ignore_index=True)
print((dur[dur.publication_month == ANALYSIS_MONTH]).to_string())

by_month = dur.groupby(["publication_month", "kind"]).matches_label.all().unstack()
print("Months where all four duration counts match their labels:", int(by_month["count"].sum()), "of", len(MONTHS))
print("Months where all four duration percentages match their labels:", int(by_month["share"].sum()), "of", len(MONTHS))
print((by_month).to_string())

table1.to_parquet(SILVER_DIR / "published_table1.parquet", index=False)
table2.to_parquet(SILVER_DIR / "published_table2_national_day_time.parquet", index=False)
dur.to_csv(EVIDENCE_DIR / "silver_duration_label_check.csv", index=False)
oc_summary.to_csv(EVIDENCE_DIR / "silver_outcome_sum_check.csv")
practice_match.to_csv(EVIDENCE_DIR / "silver_practice_match.csv", index=False)
print("Silver outputs:")
for p in sorted(SILVER_DIR.rglob("*")):
    if p.is_file():
        print(f"  {p.relative_to(PROJECT_DIR)}  ({p.stat().st_size / 1e6:.1f} MB)")
