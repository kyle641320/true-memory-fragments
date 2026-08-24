# r19 batch plan

- task1: compact hash newCapacity helper
- task2: compact hash map bucket flood threshold helper

Protocol:
1. real model produces intent JSON only
2. runner checks stale-boundary evidence
3. stale action blocks first
4. reread current source
5. fresh intent allowed
6. hidden scorer + compile gate decide pass/fail
