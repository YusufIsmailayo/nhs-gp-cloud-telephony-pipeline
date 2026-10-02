# NHS GP Cloud Based Telephony Pipeline

A Bronze → Silver → Gold pipeline over NHS England Digital's
[Cloud Based Telephony Data in General Practice](https://digital.nhs.uk/data-and-information/publications/statistical/cloud-based-telephony-data-in-general-practice)
(official statistics in development), joined to registered-list sizes so that coverage
can be stated as a share of **patients**, not just a share of practices.

**Status: planning. No findings yet.** Nothing in this repo should be quoted until the
reconciliation gate in `03_gold` passes.

## The question

August 2026: 27,160,966 inbound calls to 5,327 participating practices (86.3% of open and
active practices); 15,675,776 (57.7%) answered by practice staff; 2,817,449 (10.4%)
abandoned in the queue. Before any of those rates is treated as national, I want to know:

1. **Coverage by patients.** What share of the registered population sits behind the
   missing 13.7% of practices, and do the missing practices skew by region, deprivation
   or supplier?
2. **The remainder.** Answered plus abandoned is 68.1%. The other 8,667,741 calls (31.9%)
   are handled some other way — the breakdown comes from the file, not from assumption.
3. **Monday 08:00–10:00.** Rebuild the published 2,037,943 (7.5%) rather than take it on
   trust. Note August 2026 had five Mondays, one of them the Summer Bank Holiday (31st).

## Reconciliation gate (runs before anything new is derived)

| Published figure | Must reproduce |
|---|---|
| Inbound calls, Aug 2026 | 27,160,966 |
| Abandoned in queue | 2,817,449 (10.4%) |
| Answered by practice staff | 15,675,776 (57.7%) |
| Participating practices | 5,327 |
| Coverage | 86.3% → implies ~6,169–6,176 open and active practices |

## Sources

See `docs/sources.md` for exact files, join keys and the open questions still to settle.

## Evidence snapshots

Each Bronze load commits a dated snapshot of the publication page to
`evidence/publication_pages/<YYYY-MM>/` (raw HTML, extracted caveat text, retrieval
timestamp and SHA-256). The argument depends on what the page said on the day, and the
coverage caveat changes month to month.

## Planned structure

```
notebooks/   01_bronze.ipynb → 02_silver.ipynb → 03_gold.ipynb
src/pipeline/  scripted equivalents of the notebook logic
data/        bronze / silver / gold Parquet (gitignored)
evidence/    publication-page snapshots (committed)
docs/        sources.md, data_dictionary.md
```

## Author

Yusuf Ismail — Data Engineer | NHS & Public Sector Analytics
[GitHub](https://github.com/YusufIsmailayo) | [Medium](https://medium.com/@yusufismail_91982)
