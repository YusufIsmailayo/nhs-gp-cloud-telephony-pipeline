# Sources, join keys and open questions

Status as of 2 October 2026: none of these files has been opened yet — the build
environment could not reach digital.nhs.uk. Everything marked *to confirm* is an
expectation, not a verified fact.

## Files

| Need | Source | Join key | Status |
|---|---|---|---|
| Telephony, Aug 2026 + back series | NHS England Digital, Cloud Based Telephony Data in General Practice, monthly pages (`.../<month>-<year>`). Back series reaches at least October 2025 — full list from the series index page | ODS practice code | to confirm file names, columns, grain |
| Outcome definitions | Series "Supporting Information" page | — | to confirm |
| Registered list size | NHS England Digital, Patients Registered at a GP Practice, 1 August 2026 snapshot (practice totals + practice→PCN/sub-ICB/ICB/region mapping) | ODS practice code | to confirm |
| Practice register (denominator) | ODS `epraccur` — status, prescribing setting (4 = GP practice), postcode | ODS practice code | to confirm |
| Deprivation | Fingertips practice-level IMD (registered-population-weighted), not practice-postcode IMD | ODS practice code | to confirm vintage (IMD 2019 vs 2025) |

## Join rules

- Key: 6-character ODS practice code; trim and upper-case before joining.
- Report unmatched codes in both directions — never drop them silently.
- Check practices that merged, closed or opened during the reference month.
- List-size snapshot: 1 August 2026, to align with the call month.

## Open questions

1. Can 86.3% be rebuilt? 5,327 / 0.863 implies ~6,169–6,176 open and active practices.
   If no source reproduces that denominator, the patient share inherits the same doubt.
2. Supplier skew may not be testable at practice level. The telephony file can only name
   a supplier for practices that submitted; I know of no public practice-level register
   of telephony suppliers. Clinical system supplier (EMIS/TPP) is a different thing and
   must not be used as a proxy.
3. Are the outcome categories mutually exclusive? Expected categories: answered, missed
   (voicemail counted as missed), call back requested, ended by automated message or
   diversion, abandoned. Test that they sum to inbound before quoting the 31.9% breakdown.
4. Is hour-of-week data published per practice or only nationally? This decides whether
   the Monday 08:00–10:00 figure can be split by coverage, and whether the 168-cell chart
   can be anything other than national.
