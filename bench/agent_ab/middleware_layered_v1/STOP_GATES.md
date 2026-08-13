# Frozen execution gates
1. Freeze protocol, manifest, tasks, goldens, audit, scorer, runner, and this file before execution.
2. Run one-sequence smoke. Stop if any mechanism gate fails.
3. Only then run all five sequences. Do not tune rules after observing results.
4. Run experiment tests, full unittest suite, pycompile, frozen hash verification, diff check, machine audit and human report.
