# Independent audit of TMF fullscale experiment

Status: **PASS**

- Run dirs / samples / execution order: 160 / 160 / 160
- Missing required archived files: 0
- Order mismatches: 0
- Primary field mismatches vs runner: 0
- Frozen SHA mismatches: 0
- Prompt unique-variable proof OK: True

## Recomputed primary result

- control: valid 80, stale_error 80, correct 0, stale_rate 100.0%
- treatment: valid 80, stale_error 8, correct 72, stale_rate 10.0%
- Fisher two-sided p: `2.1326174722623323e-12`
- Absolute stale-error reduction: `0.900`; Newcombe 95% CI: `(0.8033434772528575, 0.9484523844326191)`
- Group stale-error counts: control [8, 8, 8, 8, 8, 8, 8, 8, 8, 8]; treatment [1, 1, 1, 0, 0, 1, 1, 2, 1, 0]

## Secondary metric, from archived runner score

- reread_f: control 31/80; treatment 80/80
- direct_probe_f: control 0/80; treatment 0/80

## Audit notes

Primary result was independently rederived from archived generated code and archived current fixture. Secondary `reread_f` was not rederived exactly because task-start timestamps were not persisted separately; this does not affect the primary stale-error/correctness conclusion.
