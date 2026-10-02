# Sources, join keys and open questions

Status as of 2 October 2026: all sources downloaded (`src/pipeline/download_bronze.py`)
and profiled. Every downloaded file, with source URL, timestamp and SHA-256, is listed in
`evidence/download_manifest_2026-10-02.txt`. Only August 2026 telephony is committed; the
Oct 2025 – Jul 2026 back series (~330 MB) is re-downloaded by the script.

## Files

| Need | Source | Join key | Status |
|---|---|---|---|
| Telephony, Aug 2026 + back series | NHS England Digital, Cloud Based Telephony Data in General Practice, monthly pages (`.../<month>-<year>`). 11 published months, Oct 2025 – Aug 2026 (Sep and Oct 2026 pages exist but are "Upcoming, not yet published") | `PRACTICE_CODE` | downloaded — see below |
| Outcome definitions | Series "Supporting Information" page | — | snapshot taken; definitions not yet read |
| Registered list size | NHS England Digital, Patients Registered at a GP Practice, 1 August 2026: `gp-reg-pat-prac-all` (practice totals) + `gp-reg-pat-prac-map` (practice→PCN/sub-ICB/ICB/region) | `CODE` / `PRACTICE_CODE` | downloaded — 6,129 practices |
| Practice register (denominator) | ODS `epraccur` — status, prescribing setting (4 = GP practice), postcode | column 1 (no header row) | downloaded — 15,659 rows × 27 cols; headers to apply from ODS spec |
| Deprivation | Fingertips practice-level IMD (registered-population-weighted), not practice-postcode IMD | ODS practice code | not yet downloaded; vintage to confirm (IMD 2019 vs 2025) |

### Telephony files per month

| File | Grain | Columns | Aug 2026 rows |
|---|---|---|---|
| By Day and Time `.zip` (8 CSVs: 7 regions + Unmapped) | practice × date × time band × indicator | `Date, REGION_CODE, ICB_CODE, SUB_ICB_LOCATION_CODE, PCN_CODE, PRACTICE_CODE, Indicator, Time_Category, Value` | 3,798,314 |
| By Durations `.zip` | practice × date × duration bucket × indicator | as above, `Duration` in place of `Time_Category` | 2,689,158 |
| Calls Answered Metric `.zip` — **Jun 2026 onwards only** | practice × date × wait bucket × core period | as above + `Wait_Time`, `Core_Category` (`Core_8_10`, core 10:00–18:30, `Non-Core`) | 1,520,690 |
| Publication Summary `.xlsx` | Table 1 coverage series (Mar 2025 →); Table 2 national by date × band; Tables 3/4a/4b/5 per practice | — | ~5,100 practice rows |
| Participation and submission by practice `.xlsx` | practice | — | ~6,170 |
| Metadata `.xlsx` | column descriptions | — | — |

Indicators in the CSVs: `CBT001`–`CBT007` (`CBT001` = inbound calls, `CBT003` = answered
by wait time); the rest still to map from the metadata. Some files were reissued
(`_v2` in Oct/Nov 2025, `_0526` in Mar 2026) — use the version on the page at download.

## Join rules

- Key: 6-character ODS practice code; trim and upper-case before joining.
- Report unmatched codes in both directions — never drop them silently.
- Check practices that merged, closed or opened during the reference month.
- List-size snapshot: 1 August 2026, to align with the call month.
- The CSVs contain `PRACTICE_CODE = "Unassigned"` rows (region `Unmapped`); keep them in
  national totals, exclude them from practice-level joins, and report their volume.

## Findings from profiling (August 2026)

- **Monday 08:00–10:00 reproduced.** Sum of `CBT001`, Mondays, `08:00-09:59` = 2,037,943,
  matching the published figure exactly. Per Monday: 493,284 / 499,829 / 491,200 /
  483,014 / **70,616** (31 Aug, Summer Bank Holiday).
- **Time bands are 2-hourly, not hourly:** 00–06, 06–08, 08–10, 10–12, 12–14, 14–16,
  16–18, 18:00–18:29, 18:30–24. The metadata's example value ("09:00 - 09:59") is
  misleading. The planned 168-cell hour-of-week chart becomes 7 days × 9 bands.
- **2,817,449 is "Missed", not "abandoned in queue".** Summary Table 3 outcomes:
  answered 15,675,776 (57.7%), ended during IVR stage 6,866,642 (25.3%), call back
  requested 1,802,007 (6.6%), missed 2,817,449 (10.4%). The README label needs correcting.
- **Outcomes over-sum by 908.** The four outcomes total 27,161,874 against 27,160,966
  inbound.
- **Denominator is published.** Summary Table 1: 6,171 open active practices,
  5,327 included (0.863).
- **Patient coverage is published.** Summary Table 1: 55,333,523 of 63,257,431 registered
  patients are at included practices (87.5%, computed — slightly above practice coverage).
- **Practice-level CSVs hold 4,990 distinct practice codes** against 5,327 included
  practices. Unexplained; reconcile in Silver.
- Registered-patients files hold 6,129 practices against 6,171 open active practices.

## Open questions

1. ~~Can 86.3% be rebuilt?~~ Published directly: 5,327 / 6,171 (Summary Table 1). Still to
   confirm whether `epraccur` reproduces 6,171 independently.
2. Supplier skew may not be testable at practice level. The telephony file can only name
   a supplier for practices that submitted; I know of no public practice-level register
   of telephony suppliers. `SUPPLIER_NAME` in `gp-reg-pat-prac-map` is the clinical
   system supplier (EMIS/TPP) — a different thing that must not be used as a proxy.
3. Are the outcome categories mutually exclusive? **No, not exactly:** they over-sum
   inbound by 908 in August 2026. Read the Supporting Information definitions to explain
   the overlap before quoting the 31.9% breakdown.
4. ~~Is hour-of-week data published per practice?~~ Yes — day × 2-hour band per practice,
   so the Monday 08:00–10:00 figure can be split by coverage, region or practice.
5. Why do the practice-level CSVs contain 4,990 practices when 5,327 are included?
   Candidates: multi-practice accounts (participation file note 2–3), practices with
   zero calls, or the `Unassigned` rows.
