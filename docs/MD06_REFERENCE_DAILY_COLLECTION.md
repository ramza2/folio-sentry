# MD06A/B — Reference-only daily collection core

## Runtime contract (not deployed)
- One-shot CLI: `python -m app.md06_daily_collector --market KR --confirm-reference-collection` (or US).
- Requires independent auto-collect and storage switches, both default off; token issue independently default off. Uses the existing MD05 private key/state bind mounts, not another token cache.
- Intended schedule: Tue–Sat 07:00 in Asia/Seoul / America/New_York respectively (DST-aware). Valid window 06:00–12:00 local; scheduler wiring/installation remains separate. This is a schedule heuristic, not a statement of exchange holidays.
- 90 calendar days inclusive, ending yesterday in the exchange-local timezone; one daily history request per registered active instrument. Actual provider coverage may be shorter. No pagination or retry. Maximum 15 per market; larger lists fail explicitly rather than silently starve some instruments.
- Durable per-market/day attempt marker and shared collector lock; failed or interrupted runs are not automatically retried. DB schema must have an installed price_bar migration before any credentials/requests. Recheck registration in the write transaction. No connection is held during provider I/O.
- Auto caller's shared rolling 24h cap is 40 total HTTP reservations, including manual requests and token issuance. Manual cap remains 60. Token+quote requires two available slots when issue is necessary; 24h issuance gap and quote spacing remain unchanged. No increase to provider limits.
- Store prior-date weekday RAW OHLCV only, numeric validation and receipt checks; quality_status=PARTIAL/is_final=false/source_observed_at=null. Reference-only policy is deliberately distinct from the strict calendar-attested ingestion boundary. It does not establish an open trading session, finalized close, corporate action correctness or signal eligibility.
- Same key/same values is NOOP; a changed historical bar rejects that entire instrument batch and stops the run, never silently replaces an earlier observation. Separate correction policy and coverage/status UI are later work. All output counts only; no symbols, holdings, keys, tokens or upstream errors.
- No operation is enabled by installing code. Production still portfolio01; additive schema migration, updated Backend deployment, runtime preflight, timer configuration and actual automated KIS usage require separate approval. No Frontend/Compose changes in this PR.

## Validation
Synthetic runner/window/DST/duplicate lock/error/default-off tests, shared quota boundary tests, isolated PostgreSQL reference history insert/no-op/conflict tests. Existing strict attested and manual API tests remain regression gates.
