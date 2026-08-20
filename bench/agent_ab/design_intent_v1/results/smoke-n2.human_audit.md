# design_intent_v1 Human Audit Template

Machine scoring is primary for freshness/read telemetry; humans audit design-intent score (0/1/2).

## B01

### SOURCE_ONLY
- Machine design score: 0
- Chain completeness: 0.00
- Source bytes read: 28028
- Human score (0/1/2): TBD
- Answer excerpt: 

### TMF_STALE
- Machine design score: 0
- Chain completeness: 0.00
- Source bytes read: 28111
- Human score (0/1/2): TBD
- Answer excerpt: 

### TMF_FRESH
- Machine design score: 0
- Chain completeness: 0.00
- Source bytes read: 25469
- Human score (0/1/2): TBD
- Answer excerpt: 

## B02

### SOURCE_ONLY
- Machine design score: 0
- Chain completeness: 0.00
- Source bytes read: 25469
- Human score (0/1/2): TBD
- Answer excerpt: 

### TMF_STALE
- Machine design score: 0
- Chain completeness: 0.00
- Source bytes read: 28038
- Human score (0/1/2): TBD
- Answer excerpt: 

### TMF_FRESH
- Machine design score: 2
- Chain completeness: 1.00
- Source bytes read: 12456
- Human score (0/1/2): TBD
- Answer excerpt: The rename breaks every concrete `Dispatcher` implementation because all still call `Subscriber.dispatchEvent`: `PerThreadQueuedDispatcher.dispatch` calls it while draining its per-thread queue; `LegacyAsyncDispatcher.dispatch` calls it while draining the global `EventWithSubscriber` queue; and `ImmediateDispatcher.dispatch` calls it while iterating subscribers. Therefore the upstream `EventBus.post` → `Dispatcher.dispatch` path is transitively broken for every dispatch mode, including the dispatcher that preserves legacy `AsyncEventBus` behavior. The full intended chain is `EventBus.post` → `Dispatcher.dispatch` → `Subscriber.dispatchEvent` (now `enqueueEventForDispatch`) → `Executor.execut

