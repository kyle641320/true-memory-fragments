# R20 Scenario 1 Execution Notes

Task:
- Add a refresh-completion hook in the Guava cache refresh path.

Key risk:
- A-only reasoning may place the hook too early, at refresh initiation instead of completion.

TMF expectation:
- stale boundary detection should force reread of the reload/future completion boundary before patching.

Oracle:
- hook should fire only after refresh completion/publication.

Arms:
- SOURCE_ONLY
- TMF_PROTECT
