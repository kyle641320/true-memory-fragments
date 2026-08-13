# cognitive_continuity_v1 protocol (frozen before execution)

This paired experiment measures second-and-later use by one **logical** cognitive subject across stateless broker calls. Phase A and B share `logical_agent_id` and `workflow_id`; this is persistence in an explicit cognitive layer, not model hidden state. Phase A must autonomously search/read real source and complete a first task. Its tool trace creates source-hash-bound memory with IDs/provenance.

Phase B is a different downstream task over the same region. Both arms receive the same minimal envelope: IDs, prior-task-complete, memory IDs and provenance only—no source, answer, transcript, or golden. TMF additionally receives fresh claims only when deterministic prior trace path/symbol/hash gates match, before the first B read. SOURCE receives no claims and normally rereads. Injection tokens count.

Arms use identical model, task, autonomous JSON tool loop, limits, temporary fixture repositories, and frozen randomized order. Prompts do not name target paths. Repeated metrics count only B reads overlapping A-read files/regions. Understanding is scored by structured answer+citation; edits by clean task tests/diff assertions. Adoption is mechanical: correct cited use or successful patch/test before rereading a covered region, never self-report.

Semantic pairs mutate source after A: old claims must be stale, old facts are withheld, and a localized affected-file read is required before final/edit. Unknown/unrelated are safety controls. Error classes: memory-caused, stale-memory, post-reread, baseline, output-contract, runtime. N is descriptive; no significance claim.
