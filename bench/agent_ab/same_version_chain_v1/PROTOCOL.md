# same_version_chain_v1 Protocol

Three-arm same-version coding experiment over the same pristine Guava EventBus fixture.

- SOURCE_ONLY: source listing only.
- TMF_CLAIMS: Phase A call-chain claims saved under `.tmf/` and injected into Phase B.
- DOC_CONTROL: manually written prose with equivalent chain information.

No version mutation is used.

Harness requirements implemented in `runner.py`:
- `read_range(file,start,end)` and `read_symbol(file,symbol)` tools.
- Complete raw transcript per run under `results/raw/`.
- JSON-action protocol with natural-language tolerance and repair prompts.
- 24-turn budget.
- Machine audit: compile, task-specific trap checks, golden-node coverage, reads/tool calls/tokens/wall time.
