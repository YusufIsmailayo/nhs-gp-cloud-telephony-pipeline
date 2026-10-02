# Sources, join keys and open questions

Status as of 2 October 2026: all sources downloaded (`src/pipeline/download_bronze.py`),
Bronze, Silver and Gold built (`notebooks/01_bronze.ipynb` → `03_gold.ipynb`). Every
downloaded file, with source URL, timestamp and SHA-256, is listed in
`evidence/download_manifest_2026-10-02.txt`. Only August 2026 telephony is committed; the
Oct 2025 – Jul 2026 back series (~330 MB) is re-downloaded by the script.

## Files

| Need | Source | Join key | Status |
|---|---|---|---|
| Telephony, Aug 2026 + back series | NHS England Digital, Cloud Based Telephony Data in General Practice, monthly pages (`.../<month>-<year>`). 11 published months, Oct 2025 – Aug 2026 (Sep and Oct 2026 pages exist but are "Upcoming, not yet published") | `PRACTICE_CODE` | in Silver |
| Outcome and indicator definitions | Series "Supporting Information" page (last edited 6 May 2026) | — | read; applied in Silver Step 1 |
| Registered list size | NHS England Digital, Patients Registered at a GP Practice, 1 August 2026: `gp-reg-pat-prac-all` (practice totals) + `gp-reg-pat-prac-map` (practice→PCN/sub-ICB/ICB/region) | `CODE` / `PRACTICE_CODE` | in Silver — 6,129 practices, 63,237,908 patients |
| Practice register (denominator check) | ODS `epraccur`, 2 Oct 2026 — status, role code (`RO76` = GP practice), postcode. Column layout from the ODS Data Search & Export reference catalogue (snapshot in `evidence/reference/`) | `practice_code` | in Silver — columns named from the spec |
| Deprivation | Fingertips indicator 94240, "Deprivation score (IMD 2025)", GP practice level (area type 7), 6,143 practices. Higher score = more deprived. Method: see open question 7 | `Area Code` = ODS practice code | in Silver — 6,094 of the 6,171 August practices matched |

### Telephony files per month

| File | Grain | Columns | Aug 2026 rows |
|---|---|---|---|
| By Day and Time `.zip` (8 CSVs: 7 regions + Unmapped) | practice × date × time band × indicator | `Date, REGION_CODE, ICB_CODE, SUB_ICB_LOCATION_CODE, PCN_CODE, PRACTICE_CODE, Indicator, Time_Category, Value` | 3,798,314 |
| By Durations `.zip` | practice × date × duration bucket × indicator | as above, `Duration` in place of `Time_Category` | 2,689,158 |
| Calls Answered Metric `.zip` — **Jun 2026 onwards only** | practice × date × wait bucket × core period | as above + `Wait_Time`, `Core_Category` (`Core_8_10`, core 10:00–18:30, `Non-Core`) | 1,520,690 |
| Publication Summary `.xlsx` | Table 1 coverage series (Oct 2024 →); Table 2 national by date × band; Tables 3/4a/4b/5 per practice | — | ~5,100 practice rows |
| Participation and submission by practice `.xlsx` | practice | — | ~6,170 |
| Metadata `.xlsx` | column descriptions (does not define the indicators) | — | — |

### Indicators (Supporting Information page)

| Code | Meaning |
|---|---|
| CBT001 | All external inbound calls |
| CBT002 | Ended during the IVR (automated routing) stage |
| CBT003 | Answered by practice staff, by wait-time bucket |
| CBT004 | Missed: ended unanswered while queuing or ringing, **including voicemail** |
| CBT005 | Virtual-queue callback requested |
| CBT006 | Automatic callback made |
| CBT007 | Answered by practice staff, by call-duration bucket (should equal CBT003) |

"Dealt with" = answered + ended in IVR + callback requested. "Not dealt with" = missed.
Some files were reissued (`_v2` in Oct/Nov 2025, `_0526` in Mar 2026); the column layout is
identical in every month.

## Join rules

- Key: 6-character ODS practice code; trim and upper-case before joining (no codes
  actually needed changing).
- Report unmatched codes in both directions — never drop them silently.
- Check practices that merged, closed or opened during the reference month.
- List-size snapshot: 1 August 2026, to align with the call month.
- `PRACTICE_CODE = "Unassigned"` = calls from a **phone account shared by several
  practices**, which NHS England can't split. Count them nationally, and at region / ICB /
  sub-ICB / PCN level wherever that code is populated (geography is filled in as far down
  as all the account's practices share it), but never at practice level. Every row with
  region `Unmapped` is Unassigned; most Unassigned rows are *not* Unmapped.
- `SUPPLIER_NAME` in the registered-patients mapping is the **clinical system** supplier
  (EMIS/TPP). Silver renames it `clinical_system_supplier` so it can't be mistaken for the
  telephony supplier.

## Findings (August 2026 unless stated)

### From profiling

- **Monday 08:00–10:00 reproduced.** Sum of `CBT001`, Mondays, `08:00-09:59` = 2,037,943,
  matching the published figure exactly. Per Monday: 493,284 / 499,829 / 491,200 /
  483,014 / **70,616** (31 Aug, Summer Bank Holiday).
- **Time bands are 2-hourly, not hourly:** 00–06, 06–08, 08–10, 10–12, 12–14, 14–16,
  16–18, 18:00–18:29, 18:30–24. The metadata's example value ("09:00 - 09:59") is
  misleading. The planned 168-cell hour-of-week chart becomes 7 days × 9 bands.
- **2,817,449 is "Missed", not "abandoned in queue".** Outcomes: answered 15,675,776
  (57.7%), ended in IVR 6,866,642 (25.3%), callback requested 1,802,007 (6.6%), missed
  2,817,449 (10.4%). README corrected.
- **Coverage is published.** Summary Table 1: 6,171 open active practices, 5,327 included
  (0.863); 55,333,523 of 63,257,431 registered patients at included practices (0.875).

### From Silver

- **The 4,990-vs-5,327 practice gap is explained.** 5,327 included = 4,977 on their own
  phone account (every one has its own call rows) + 350 on shared accounts (calls in the
  Unassigned block). 12 of the 350 are still published under their own code because the
  account lists only themselves (participation note 3: excluded practices aren't listed).
  4,977 + 12 = 4,989 practice codes; nothing missing. Holds in all 11 months.
- **Shared-account calls are 1,749,178 (6.4% of inbound).** Placeable at region 90.6%,
  ICB 84.9%, sub-ICB 74.6%, PCN 39.3%.
- **The three call files agree.** Every indicator present in more than one file has the
  same national total in each, in every month.
- **Outcomes nearly always add up.** 4,881 of 4,989 practices (98%) have outcomes exactly
  equal to inbound. The national +908 is net of 1,720 gross mismatched calls. October
  2025 was much worse (about 1,000 practices off, −20,288 net). CBT003 = CBT007 for every
  practice except three single-month blips.
- **Duration percentages are mislabelled in Table 1 from the January 2026 edition.** The
  four duration counts match their labels in all 11 editions (rebuilt from CBT007). The
  four percentages match only in the Oct–Dec 2025 editions. From January 2026 each sits
  one row off: the published "1 minute or less: 8.3%" is the over-5-minutes share; the true
  1-minute-or-less share is 22.8%. Gold uses rebuilt shares.
- **Published patient denominators are revised.** "Registered patients at included
  practices" (and the rate per 1,000 built on it) is restated for back months in later
  editions. Gold uses the August 2026 edition throughout.
  `evidence/silver_table1_revisions.csv` lists every changed value.
- **Wait-time series break, June 2026** (Table 1 note 5): a supplier corrected its
  wait-time method; earlier months were not corrected.
- **42 participating practices have no 1 August registered-patient row.** Their patient
  counts are unknown here, not zero.
- **IMD 2025 coverage.** 77 participating practices have no Fingertips score (67 not
  included; 12,197 patients in total). 49 Fingertips practices aren't on the August list;
  all 49 are dormant or inactive in epraccur.

### From Gold: deprivation

- **The most deprived fifth of practices is the least covered.** Patient coverage by
  practice IMD 2025 quintile (equal numbers of practices, national cut points): Q1 83.4%,
  Q2 87.1%, Q3 86.5%, Q4 90.7%, Q5 88.8%.
- **Region explains part of it, not all.** Q1 is 4.9 points below Q2–Q5 (88.3%). Given its
  regional mix, Q1 would be at about 86.9%, so region accounts for 1.4 points and 3.5 remain.
  The North West (−8.4 points within the region) and Midlands (−7.4) contribute −4.1 points
  between them; North East and Yorkshire runs the other way (+5.0 within the region,
  offsetting 1.4).
- **Most deprived practices get more calls per patient**: 28.7 per 1,000 patients per
  working weekday in Q1 against 22.1 in Q5. Answered and missed shares are similar across
  quintiles.

## Open questions

1. ~~Can 86.3% be rebuilt?~~ Published directly (5,327 / 6,171), and `epraccur`
   reproduces the denominator to within timing: 6,163 of the 6,171 are still active on
   2 October, the other 8 have since gone dormant, and epraccur adds 2 active practices
   not on the list.
2. Supplier skew may not be testable at practice level. The telephony file can only name
   a supplier for practices that submitted; I know of no public practice-level register
   of telephony suppliers. The Supporting Information page lists suppliers onboarded but
   not which practice uses which. The clinical system supplier must not be used as a proxy.
3. ~~Are the outcome categories mutually exclusive?~~ Not guaranteed. The Supporting
   Information page says a call can fall outside the call flow or be counted under more
   than one outcome. Measured in Silver: 98% of practices add up exactly in August 2026.
4. ~~Is hour-of-week data published per practice?~~ Yes — day × 2-hour band per practice,
   so the Monday 08:00–10:00 figure can be split by coverage, region or practice.
5. ~~Why do the practice-level CSVs contain 4,990 practices when 5,327 are included?~~
   Shared phone accounts — see Silver findings.
6. ~~Does NHS England compute "registered patients at open active practices" from a
   different list snapshot?~~ No. Tested against the 1 July, 1 August and 1 September 2026
   snapshots: 1 August is closest for August (and 1 July for July), so NHS England uses the
   same-month list. The remaining gap (−19,523 open active, −4,333 included; 0.03%) sits
   entirely in the 42 participating practices with no 1 August list row. 41 aren't included
   and are almost all services holding no registered list (walk-in centres, extended-access
   hubs); the one included is Berrylands Surgery (H84053, dormant, shared account). The
   source NHS England uses for those 42 isn't in any public file I hold, so the Gold gate
   marks both totals EXPLAINED. Patient coverage still matches at published precision.
7. **How exactly is Fingertips indicator 94240 built?** Its metadata gives only the name
   and source (MHCLG); the IMD 2015 and 2019 predecessors (91872, 93553) are no fuller. The
   usual practice-level method weights the IMD scores of the LSOAs where registered
   patients live, and NHS England documents that method
   (`evidence/reference/nhse_practice_imd_method_2026-10-02.html`). That's not confirmed
   for 94240. If it turned out to be practice-postcode IMD, the quintiles would describe
   practice location rather than patient population.
