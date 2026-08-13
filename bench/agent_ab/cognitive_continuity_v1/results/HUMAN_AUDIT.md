# Human audit — cognitive_continuity_v1

Frozen smoke gate **STOPPED** the experiment: 2/2 valid pairs, machine adoption 0/2 (required >=1). No full run and no prompt/mechanism tuning.

- Success: SOURCE 1/2, TMF 1/2 under frozen scoring.
- Repeated phase-B bytes over phase-A regions: SOURCE 173, TMF 47 (126 saved, all from A01).
- Total estimated tokens: SOURCE 3383, TMF 4733.
- A03 mechanical edit/tests passed in both arms, but both reread the covered file.
- A01 TMF used the injected claim without rereading and answered substantively the same as SOURCE; however the frozen scorer expected `120` while the fixture computes `110`. Both arms therefore failed machine correctness and TMF adoption could not be credited. Per protocol, this is preserved rather than regraded.
- No semantic sequence ran, so semantic safety remains unmeasured here.

Product ruling: even with explicit logical continuity, this frozen smoke did not demonstrate machine-qualified adoption. Do not claim productivity value. The run also exposed a preregistered-golden defect; a future version must correct it prospectively, never revise v1.
