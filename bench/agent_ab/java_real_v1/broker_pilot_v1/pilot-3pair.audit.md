# Broker pilot audit

- Valid pairs: 3/3
- Isolation: network blocked=True, ambient secrets=[]
- Frozen/base manifest SHA256: `d730c3910fa79e278fe348ef0768da5e2e0d260510ebff8f57151012b84fdffa`
- Pilot manifest SHA256: `02629938811b7dadb41a1c5a0fefa9cccf6f12de93db222e4149d6670b8c6821`
- Protocol SHA256: `90f66e057828d9760f6201844654fc06ecac87f9d44aa6ea87356c56c6fa6ff3`

## Preliminary held-out metrics

- SOURCE_ONLY: n=3, task accuracy=0.000, citation accuracy=0.000, transport valid=1.000, mean prompt tokens=4799.3
- TMF_MAP: n=3, task accuracy=0.000, citation accuracy=0.000, transport valid=1.000, mean prompt tokens=4881.0

Completion alone was not counted as a valid arm. No prompts, tasks, goldens, or metrics were changed after observing results.
