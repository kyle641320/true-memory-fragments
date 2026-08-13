# Blind v1 evidence-mediation review

Review order was transcripts and supplied evidence first, with arm labels and audit scores withheld; tasks/goldens were consulted only after failure coding.

## Transcript-first taxonomy

- **Retrieval omission:** one P01 response pair explicitly said the publication/consumption path was absent; the static bundle omitted the central scheduler/listener files.
- **Evidence-to-rubric mismatch:** P02 responses gave a coherent producer/listener/order account but omitted the public event declaration required by the frozen golden. P03 identified the domain edit but did not ground the booking boundary required by the golden.
- **Citation completeness, not syntax:** citations generally resolved and had line ranges, but did not cover every required causal hop.
- **Overconfident evidence-bound abstention:** P01 correctly refused to invent absent code, yet confidence was high; this is a mediation failure, not primarily a reasoning failure.
- **No navigation recovery:** neither response could ask for a missing file after inspecting initial evidence.

After unblinding, both arms shared these failure classes and both scored 0/3, so the dominant v1 failure is common-mode evidence mediation.

## v1 design diagnosis and v2 estimand

v1 was raw inference over one precomputed lexical source dump (four files) plus optional precomputed TMF context. It was not an agent choosing and revising source reads. Consequently it estimated the effect of appending TMF to a fixed dump, confounded by dump omissions—not the value of TMF during navigation.

v2 estimates the paired intention-to-treat effect of **access to TMF navigation** inside an otherwise identical deterministic two-stage loop: each arm sees the same source-file catalog, selects files once, receives exactly the same source-line budget, then answers. TMF_MAP alone receives TMF thin context during selection. Source remains authoritative.
