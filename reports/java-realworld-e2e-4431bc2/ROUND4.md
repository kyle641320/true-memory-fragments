# Java Spring contract round 4

- Added source-only, fail-closed DI resolution from an exact imported interface injection point to exactly one tracked, explicitly stereotyped source implementation. Multiple candidates remain unresolved; profiles, conditions, proxies, reflection, generated code and runtime scanning are never guessed.
- Extended Spring Data/JPA declaration evidence to exact Spring/Jakarta package wildcard imports used by pinned JHipster source. Repository generic domain type must resolve to a tracked source `@Entity`; query text remains opaque.
- Added four human-reviewed real-source repository-to-entity assertions (Petclinic Owner/PetType; JHipster BankAccount/Label).
- Derivation cache version: `java.derive.v5`.

## Gates

- Targeted Spring/JPA unittest: 33/33.
- Qualifications: 46/46 (aggregate checks all pass).
- Full unittest: 489/489.
- Pinned Petclinic/JHipster E2E: 89/89 assertions; routes 9/9; calls 6/6; repository/entity 4/4; Recall@10 0.75.

## Semantic freshness mutation

Direct source mutation of `Owner.getPets` with an independently defined semantic oracle (claims bound to that declaration): TP=8, FN=1, FP=73; precision=0.0988, recall=0.8889. After rewarm stale=0. The high FP is real conservative file/token invalidation and is not hidden behind changed-file ratio.

## Residual risks

Runtime Spring bean graph, implicit single-constructor injection, component scanning, dynamic proxies, conditional/profile activation, SpEL, reflection, generated/Lombok code, transaction effectiveness and JPA runtime/query behavior remain unknown/partial. Semantic freshness locality needs finer dependency/binding granularity: current correctness is conservative but invalidation precision is poor.
