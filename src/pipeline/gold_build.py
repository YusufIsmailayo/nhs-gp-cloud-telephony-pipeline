"""
Gold build for NHS GP Cloud Based Telephony.

Scripted equivalent of notebooks/03_gold.ipynb (generated from the same cells):
runs the August 2026 reconciliation gate against NHS England's published figures,
then builds the Monday 08:00-10:00, coverage-by-region, outcomes, monthly trend and
call-duration cuts. Run after src/pipeline/silver_build.py.
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[2]

BRONZE_DIR = PROJECT_DIR / "data" / "bronze"
SILVER_DIR = PROJECT_DIR / "data" / "silver"
GOLD_DIR = PROJECT_DIR / "data" / "gold"
EVIDENCE_DIR = PROJECT_DIR / "evidence"
GOLD_DIR.mkdir(parents=True, exist_ok=True)

MONTH = "2026-08"
CORE_BANDS = ["08:00-09:59", "10:00-11:59", "12:00-13:59", "14:00-15:59", "16:00-17:59", "18:00-18:29"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

day_time = pd.read_parquet(SILVER_DIR / "calls_day_time" / f"{MONTH}.parquet")
durations = pd.read_parquet(SILVER_DIR / "calls_durations" / f"{MONTH}.parquet")
answered = pd.read_parquet(SILVER_DIR / "calls_calls_answered" / f"{MONTH}.parquet")
participation = pd.read_parquet(SILVER_DIR / "practice_participation.parquet")
practice_dim = pd.read_parquet(SILVER_DIR / f"practice_dim_{MONTH}.parquet")
registered = pd.read_parquet(SILVER_DIR / "registered_patients.parquet")
table1 = pd.read_parquet(SILVER_DIR / "published_table1.parquet")
table2 = pd.read_parquet(SILVER_DIR / "published_table2_national_day_time.parquet")

published = (table1[(table1.publication_month == MONTH) & (table1.reference_month == MONTH)]
             .set_index(["group", "measure"])["value"])
print(f"Loaded Silver for {MONTH}: {len(day_time):,} day-time rows, {len(published)} published Table 1 values")

BANK_HOLIDAYS = [pd.Timestamp("2026-08-31")]  # Summer Bank Holiday, England

dates = pd.date_range(f"{MONTH}-01", periods=pd.Period(MONTH).days_in_month)
weekdays_in_month = int((dates.dayofweek < 5).sum())
working_weekdays = weekdays_in_month - sum(d in dates for d in BANK_HOLIDAYS)
published_working = int(published[("Working Days", "Number of working weekdays")])
assert working_weekdays == published_working, (working_weekdays, published_working)
print(f"{weekdays_in_month} weekdays - {len(BANK_HOLIDAYS)} bank holiday = {working_weekdays} working weekdays "
      f"(published: {published_working})")

day_time["is_bank_holiday"] = day_time.date.isin(BANK_HOLIDAYS)

def table4b_national() -> dict:
    path = next((BRONZE_DIR / "telephony" / MONTH).glob("*Publication Summary*.xlsx"))
    raw = pd.read_excel(path, sheet_name="Table 4b", header=None)
    row = raw[raw.iloc[:, 1].astype(str).eq("National")].iloc[0]
    v = pd.to_numeric(row, errors="coerce").dropna().tolist()
    return {"inbound_any": v[0], "answered_any": v[1], "inbound_core": v[3],
            "answered_core": v[4], "inbound_8_10": v[6], "answered_8_10": v[7]}


t4b = table4b_national()
inbound = day_time[day_time.indicator.eq("CBT001")].copy()
nat = durations.groupby("indicator", observed=True)["calls"].sum()
p_all = participation[participation.month.eq(MONTH)]
pd_reg = practice_dim.set_index("practice_code")["registered_patients"]

weekday_core = inbound[~inbound.weekday.isin(["Saturday", "Sunday"]) & ~inbound.is_bank_holiday]
mon_8_10 = inbound[inbound.weekday.eq("Monday") & inbound.time_band.eq("08:00-09:59")]["calls"].sum()

answered["under_2min"] = answered.upper_s.fillna(10**9) <= 120
core = answered[answered.core_category.ne("Non-Core")]
early = answered[answered.core_category.eq("Core_8_10")]

WAIT_BANDS = {"within 1 minute": (0, 60), "within 1 to 2 minutes": (61, 120),
              "within 2 to 5 minutes": (121, 300), "after waiting over 5 minutes": (301, None)}


def wait_counts(frame):
    return {k: int(frame.loc[(frame.lower_s >= lo) & ((frame.upper_s <= hi) if hi else frame.upper_s.isna()), "calls"].sum())
            for k, (lo, hi) in WAIT_BANDS.items()}


rows = []


def check(source, label, published_value, rebuilt, kind="count", note=""):
    if kind == "count":
        ok = round(published_value) == round(rebuilt)
    elif kind == "share":
        ok = round(rebuilt, 3) == round(published_value, 3)
    else:
        ok = round(rebuilt, 1) == round(published_value, 1)
    rows.append({"source": source, "measure": label, "published": published_value, "rebuilt": rebuilt,
                 "difference": rebuilt - published_value, "status": "PASS" if ok else "FAIL", "note": note})


T1 = "Table 1"
# coverage
check(T1, "Open active practices", published[("Coverage", "Open active practices")], len(p_all))
check(T1, "Count of practices included", published[("Coverage", "Count of practices included")], int(p_all.included.sum()))
check(T1, "Practice coverage", published[("Coverage", "Practice coverage [1]")], p_all.included.mean(), "share")
reg_all, reg_inc = pd_reg.sum(), pd_reg[practice_dim.set_index("practice_code").included].sum()
check(T1, "Registered patients at open active practices",
      published[("Coverage", "Registered patients at open active practices")], reg_all)
check(T1, "Registered patients at included practices",
      published[("Coverage", "Registered patients at included practices")], reg_inc)
check(T1, "Patient coverage", published[("Coverage", "Patient coverage")], reg_inc / reg_all, "share")
check(T1, "Number of working weekdays", published_working, working_weekdays)
# calls and outcomes
total = int(inbound.calls.sum())
check(T1, "Total inbound calls", published[("Inbound calls", "Total Inbound Calls")], total)
check(T1, "Rate of inbound calls per 1,000 registered patients at included practices",
      published[("Inbound calls", "Rate of inbound calls per 1,000 patients registered at practices included")],
      total / reg_inc * 1000, "rate")
for code_, label, measure in [
    ("CBT007", "Calls answered", "Calls answered [2]"),  # Table 1 uses CBT007 (see note above the gate)
    ("CBT002", "Calls ended during the IVR stage", next(m for g, m in published.index if m.startswith("Calls ended during the IVR"))),
    ("CBT005", "Calls resulting in a call back request", "Calls resulting in a call back request [2]"),
    ("CBT006", "Call backs made", "Call backs made"),
    ("CBT004", "Missed calls", "Missed calls [2,4]"),
]:
    group = next(g for g, m in published.index if m == measure)
    check(T1, label, published[(group, measure)], int(nat[code_]))
for code_, measure in [("CBT007", "Percentage of Inbound calls answered"),
                       ("CBT002", "Percentage of Inbound calls ended during the IVR stage"),
                       ("CBT005", "Percentage of Inbound calls resulting in a call back request"),
                       ("CBT004", "Percentage of inbound calls missed")]:
    key = next((g, m) for g, m in published.index if m.startswith(measure))
    check(T1, key[1], published[key], nat[code_] / total, "share")
check(T1, "Percentage of call backs made of those requested",
      published[("Calls dealt with", "Percentage of call backs made of those requested")], nat["CBT006"] / nat["CBT005"], "share")
# wait times: any time, core hours, 8am-10am
for group, frame in [("Call wait times (any time)", answered),
                     ("Call wait times (core hours)", core),
                     ("Call wait times (8am-10am)", early)]:
    counts = wait_counts(frame)
    for band, n in counts.items():
        check(T1, f"{group}: answered {band}", published[(group, f"Calls answered {band}")], n)
    key = next((g, m) for g, m in published.index if g == group and m.startswith("Percentage of calls answered after waiting under 2"))
    check(T1, f"{group}: % answered after waiting under 2 minutes", published[key],
          frame.loc[frame.under_2min, "calls"].sum() / frame.calls.sum(), "share")
# Table 4b and the publication page
check("Table 4b", "Inbound calls, core hours (Mon-Fri 08:00-18:30)", t4b["inbound_core"],
      int(weekday_core[weekday_core.time_band.isin(CORE_BANDS)].calls.sum()),
      note="rebuilt excluding the bank holiday")
check("Table 4b", "Inbound calls, 08:00-10:00 Mon-Fri", t4b["inbound_8_10"],
      int(weekday_core[weekday_core.time_band.eq("08:00-09:59")].calls.sum()),
      note="rebuilt excluding the bank holiday")
check("Table 4b", "Answered calls, core hours", t4b["answered_core"], int(core.calls.sum()))
check("Table 4b", "Answered calls, 08:00-10:00", t4b["answered_8_10"], int(early.calls.sum()))
check("Publication page", "Inbound calls Monday 08:00-10:00", 2_037_943, int(mon_8_10),
      note="rebuilt INCLUDING the bank holiday (31 Aug: 70,616)")
check("Publication page", "Monday 08:00-10:00 as share of inbound", 0.075, mon_8_10 / total, "share")
# Table 2: every date x band cell
t2 = table2[table2.publication_month.eq(MONTH)]
rebuilt_grid = (inbound.groupby(["date", "time_band"], observed=True)["calls"].sum().reset_index())
rebuilt_grid = pd.concat([rebuilt_grid, inbound.groupby("date")["calls"].sum().reset_index().assign(time_band="TOTAL")])
grid = t2.merge(rebuilt_grid, on=["date", "time_band"], how="outer", suffixes=("_published", "_rebuilt"))
cells_matching = int((grid.calls_published == grid.calls_rebuilt).sum())
check("Table 2", f"Date x time-band cells matching ({len(grid)} cells)", len(grid), cells_matching)

d7 = durations[durations.indicator.eq("CBT007")]
DUR_BANDS = {"1 minute or less": (0, 60), "1 to 2 minutes": (61, 120), "2 to 5 minutes": (121, 300), "over 5 minutes": (301, None)}
dur_counts = {k: int(d7.loc[(d7.lower_s >= lo) & ((d7.upper_s <= hi) if hi else d7.upper_s.isna()), "calls"].sum())
              for k, (lo, hi) in DUR_BANDS.items()}
dur_total = sum(dur_counts.values())
pub_pcts = {m.replace("Percentage of calls with a duration of ", ""): v
            for (g, m), v in published.items() if g == "Call durations" and m.startswith("Percentage")}
for band, n in dur_counts.items():
    check(T1, f"Call duration {band}", published[("Call durations", f"Duration of {band}")], n)
for band, n in dur_counts.items():
    share = n / dur_total
    own = pub_pcts[band]
    if round(share, 3) == round(own, 3):
        check(T1, f"% of calls with duration {band}", own, share, "share")
    else:
        printed_as = next((b for b, v in pub_pcts.items() if round(v, 3) == round(share, 3)), None)
        rows.append({"source": T1, "measure": f"% of calls with duration {band}", "published": own,
                     "rebuilt": share, "difference": share - own,
                     "status": "PUBLISHED LABEL ERROR" if printed_as else "FAIL",
                     "note": f"true value is printed against '{printed_as}'" if printed_as else ""})

gate = pd.DataFrame(rows)
explained = gate.measure.str.startswith("Registered patients at") & gate.status.eq("FAIL")
missing = practice_dim.loc[~practice_dim.in_registered]
gate.loc[explained, "status"] = "EXPLAINED"
gate.loc[explained, "note"] = (f"{len(missing)} participating practices have no 1 Aug 2026 list row "
                               f"({int(missing.included.sum())} included); gap is located there")
gate.to_csv(EVIDENCE_DIR / f"gold_reconciliation_{MONTH}.csv", index=False)

print(gate.status.value_counts().to_string())
assert not gate.status.eq("FAIL").any(), gate[gate.status.eq("FAIL")]
print("\nGATE PASSED: every published figure reproduced, or its gap located and explained.")
pd.set_option("display.float_format", lambda v: f"{v:,.4f}" if abs(v) < 10 else f"{v:,.0f}")
print((gate).to_string())

mon = inbound[inbound.weekday.eq("Monday")]
per_monday = (mon[mon.time_band.eq("08:00-09:59")].groupby(["date", "is_bank_holiday"])["calls"].sum()
              .reset_index().rename(columns={"calls": "calls_08_10"}))
per_monday["calls_whole_day"] = per_monday.date.map(mon.groupby("date")["calls"].sum())
normal = per_monday[~per_monday.is_bank_holiday]

weekday_avg_0810 = (weekday_core[weekday_core.time_band.eq("08:00-09:59")]
                    .groupby(["weekday", "date"], observed=True)["calls"].sum()
                    .groupby("weekday", observed=True).mean().reindex(WEEKDAYS[:5]))
monday_summary = pd.DataFrame({
    "measure": [
        "Monday 08:00-10:00, published (5 Mondays incl. bank holiday)",
        "...of which the bank holiday (31 Aug)",
        "Monday 08:00-10:00, 4 ordinary Mondays",
        "Average ordinary Monday, 08:00-10:00",
        "Average ordinary Tuesday-Friday, 08:00-10:00",
        "Ordinary Monday vs Tue-Fri average, 08:00-10:00",
        "Share of an ordinary Monday's calls arriving 08:00-10:00",
    ],
    "value": [
        mon_8_10,
        int(per_monday.loc[per_monday.is_bank_holiday, "calls_08_10"].sum()),
        int(normal.calls_08_10.sum()),
        normal.calls_08_10.mean(),
        weekday_avg_0810.iloc[1:].mean(),
        normal.calls_08_10.mean() / weekday_avg_0810.iloc[1:].mean(),
        normal.calls_08_10.sum() / normal.calls_whole_day.sum(),
    ],
})
monday_summary.to_csv(GOLD_DIR / f"monday_0810_{MONTH}.csv", index=False)
display_monday = monday_summary.copy()
display_monday["value"] = [f"{v:,.0f}" if v > 10 else (f"{v:.1%}" if v < 1 else f"{v:.2f}x") for v in monday_summary.value]
print((display_monday).to_string())

inbound["day_label"] = np.where(inbound.is_bank_holiday, "Monday (bank holiday)", inbound.weekday.astype(str))
days_per_label = inbound.groupby("day_label")["date"].nunique()
grid = (inbound.groupby(["day_label", "time_band"], observed=True)["calls"].sum()
        .unstack("time_band"))
grid = grid.div(days_per_label, axis=0).round(0).astype(int)
grid = grid.reindex(WEEKDAYS + ["Monday (bank holiday)"])
grid.insert(0, "days", days_per_label.reindex(grid.index))
grid.to_csv(GOLD_DIR / f"day_band_grid_{MONTH}.csv")
print((grid).to_string())

pdim = practice_dim.copy()
pdim["status"] = np.select([pdim.included, pdim.agreed], ["included", "agreed_not_included"], "not_agreed")
pdim["patients"] = pdim.registered_patients.fillna(0)

def coverage_table(frame, by):
    t = frame.pivot_table(index=by, columns="status", values="patients", aggfunc="sum", fill_value=0)
    n = frame.pivot_table(index=by, columns="status", values="practice_code", aggfunc="count", fill_value=0)
    out = pd.DataFrame({
        "practices": n.sum(axis=1),
        "practices_included": n.get("included", 0),
        "practice_coverage": n.get("included", 0) / n.sum(axis=1),
        "patients": t.sum(axis=1),
        "patients_not_agreed": t.get("not_agreed", 0),
        "patients_agreed_not_included": t.get("agreed_not_included", 0),
        "patient_coverage": t.get("included", 0) / t.sum(axis=1),
    })
    return out

by_region = coverage_table(pdim, "region_name")
national_row = coverage_table(pdim.assign(region_name="ENGLAND"), "region_name")
coverage = pd.concat([by_region.sort_values("patient_coverage"), national_row])
coverage["patients_outside"] = coverage.patients_not_agreed + coverage.patients_agreed_not_included
coverage.to_csv(GOLD_DIR / f"coverage_by_region_{MONTH}.csv")
print((coverage).to_string())

OUTCOMES = {"CBT003": "answered", "CBT002": "ended_in_ivr", "CBT005": "callback_requested", "CBT004": "missed"}
dd = durations[durations.indicator.isin(["CBT001", *OUTCOMES])]
reg_names = practice_dim.drop_duplicates("region_code").set_index("region_code")["region_name"]
dd = dd.assign(region=dd.region_code.astype(str).map(reg_names).fillna("UNMAPPED (shared accounts)"))
w = dd.groupby(["region", "indicator"], observed=True)["calls"].sum().unstack()
w.loc["ENGLAND"] = w.sum()
outcomes = pd.DataFrame({"inbound": w["CBT001"]})
for c, name in OUTCOMES.items():
    outcomes[name] = w[c] / w["CBT001"]
outcomes["neither_answered_nor_missed"] = outcomes.ended_in_ivr + outcomes.callback_requested
outcomes["outcome_sum_vs_inbound"] = w[list(OUTCOMES)].sum(axis=1) / w["CBT001"] - 1
outcomes = pd.concat([outcomes.drop("ENGLAND").sort_values("ended_in_ivr"), outcomes.loc[["ENGLAND"]]])
outcomes.to_csv(GOLD_DIR / f"outcomes_by_region_{MONTH}.csv")
print((outcomes).to_string())

oc = pd.read_parquet(SILVER_DIR / "practice_outcome_check.parquet")
oc = oc[oc.month.eq(MONTH) & (oc.CBT001 >= 500)].copy()
oc["ivr_share"] = oc.CBT002 / oc.CBT001
oc["answered_share"] = oc.CBT003 / oc.CBT001
oc["missed_share"] = oc.CBT004 / oc.CBT001
spread = oc[["ivr_share", "answered_share", "missed_share"]].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).T
spread["practices_with_zero"] = [(oc[c] == 0).sum() for c in spread.index]
spread.to_csv(GOLD_DIR / f"practice_outcome_spread_{MONTH}.csv")
print((spread[["count", "10%", "25%", "50%", "75%", "90%", "practices_with_zero"]]).to_string())

aug_ed = table1[table1.publication_month.eq(MONTH)].pivot_table(index="reference_month", columns=["group", "measure"], values="value")
assert not table1[table1.publication_month.eq(MONTH)].duplicated(["reference_month", "group", "measure"]).any()
UNDER_2 = next(c for c in aug_ed.columns if c[0] == "Call wait times (any time)" and c[1].startswith("Percentage of calls answered after waiting under 2"))
months = sorted(participation.month.unique())
trend = []
for m in months:
    nat_m = pd.read_csv(SILVER_DIR / "national_by_indicator_and_file.csv")
    nat_m = nat_m[nat_m.month.eq(m)].set_index("indicator")["durations"]
    pts = aug_ed.loc[m, ("Coverage", "Registered patients at included practices")]
    wd = aug_ed.loc[m, ("Working Days", "Number of working weekdays")]
    trend.append({
        "month": m,
        "practices_included": int(aug_ed.loc[m, ("Coverage", "Count of practices included")]),
        "patient_coverage": aug_ed.loc[m, ("Coverage", "Patient coverage")],
        "inbound_calls": int(nat_m["CBT001"]),
        "calls_per_1000_patients": nat_m["CBT001"] / pts * 1000,
        "working_weekdays": int(wd),
        "calls_per_1000_patients_per_working_day": nat_m["CBT001"] / pts * 1000 / wd,
        "answered": nat_m["CBT007"] / nat_m["CBT001"],
        "ended_in_ivr": nat_m["CBT002"] / nat_m["CBT001"],
        "callback_requested": nat_m["CBT005"] / nat_m["CBT001"],
        "missed": nat_m["CBT004"] / nat_m["CBT001"],
        "answered_under_2min_published": aug_ed.loc[m, UNDER_2],
        "wait_time_series_break": m >= "2026-06",
    })
trend = pd.DataFrame(trend).set_index("month")

# Do the monthly CSVs still agree with the latest (August 2026) edition of Table 1?
latest = aug_ed.loc[months, [("Inbound calls", "Total Inbound Calls"), ("Calls dealt with", "Calls answered [2]")]]
latest.columns = ["inbound_latest_edition", "answered_latest_edition"]
nat_all = pd.read_csv(SILVER_DIR / "national_by_indicator_and_file.csv").pivot(index="month", columns="indicator", values="durations")
vs_latest = latest.join(nat_all[["CBT001", "CBT007"]].rename(columns={"CBT001": "inbound_csv", "CBT007": "answered_csv"}))
vs_latest["inbound_revision"] = vs_latest.inbound_latest_edition - vs_latest.inbound_csv
vs_latest["answered_revision"] = vs_latest.answered_latest_edition - vs_latest.answered_csv
revised_months = vs_latest[(vs_latest.inbound_revision != 0) | (vs_latest.answered_revision != 0)]
KNOWN_REVISIONS = ["2025-11"]  # restated upward from the Jan 2026 edition; the Nov CSVs were not reissued
assert set(revised_months.index) <= set(KNOWN_REVISIONS), revised_months
trend["revised_after_publication"] = trend.index.isin(revised_months.index)
print("Months whose call totals were revised after their CSVs were published:")
print(revised_months[["inbound_revision", "answered_revision"]].to_string())
trend.to_csv(GOLD_DIR / "monthly_trend.csv")
print((trend).to_string())

dur_rows = []
for m in months:
    d = pd.read_parquet(SILVER_DIR / "calls_durations" / f"{m}.parquet")
    d = d[d.indicator.eq("CBT007")]
    counts = {k: d.loc[(d.lower_s >= lo) & ((d.upper_s <= hi) if hi else d.upper_s.isna()), "calls"].sum()
              for k, (lo, hi) in DUR_BANDS.items()}
    tot = sum(counts.values())
    dur_rows.append({"month": m, **{k: v / tot for k, v in counts.items()}, "answered_calls": tot})
duration_shares = pd.DataFrame(dur_rows).set_index("month")
duration_shares.to_csv(GOLD_DIR / "call_duration_shares.csv")
print((duration_shares).to_string())
