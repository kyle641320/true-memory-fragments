# Claim 6 Status — Product ROI / cost-adjusted value

## Claim

TMF provides enough product ROI to justify its token/read/tool overhead in real development workflows.

## Proof standard

A product ROI claim requires:

1. Multi-fixture, multi-repo correctness uplift.
2. Cost accounting: token count, tool calls, source reads, wall time.
3. Harness-noise-adjusted pass rates.
4. Evidence that avoided semantic failures outweigh added overhead.
5. Stability across multiple task families, not only stale-context synthetic fixtures.

## Current evidence

Positive correctness evidence exists in scoped stale-context tasks:

- M21 corevalue smoke R1: TMF 1/1, all three controls 0/1.
- M21 combined stale-control comparison: stale controls 0/7, TMF 5/7.
- Earlier M16 evidence: TMF recovered hidden invariant in many runs while SOURCE_ONLY/PREREAD failed.

Cost/overhead evidence is incomplete:

- Earlier M16 notes showed TMF used more tool/source reads than STALE_DOC_CONTROL.
- There is no standardized cost-adjusted score across the validated fixture set.
- No broad multi-repo productivity benchmark is complete.

## Result

Claim 6 is **not proven**.

Current defensible statement:

> TMF has scoped-positive correctness value in stale-context safety. Product ROI remains unproven and needs cost-adjusted, multi-fixture validation.

## Next evidence needed

- Define a cost-adjusted score, e.g. hidden-oracle pass uplift per additional source-read/tool-call/token.
- Run M21-style stale traps plus at least two non-order/non-payment fixtures.
- Report raw pass, semantic-adjusted pass, protocol-clean pass, and overhead separately.
