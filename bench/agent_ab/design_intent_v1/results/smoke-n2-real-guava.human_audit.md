# design_intent_v1 Human Audit Template

Machine scoring is primary for freshness/read telemetry; humans audit design-intent score (0/1/2).

## B01

### SOURCE_ONLY
- Machine design score: 2
- Chain completeness: 1.00
- Source bytes read: 14821
- Human score (0/1/2): TBD
- Answer excerpt: The lost design property is **broadcast/fan-out delivery**: `EventBus.post` promises to post an event to *all* registered matching subscribers, and the dispatcher contract receives the complete matching-subscriber iterator. `ImmediateDispatcher.dispatch` is intended to remove queueing and provide immediate, depth-first ordering—not to change the recipient set. Its loop therefore normally calls `Subscriber.dispatchEvent(event)` for every iterator element.  With first-match-only behavior, the concrete chain becomes `EventBus.post` → `SubscriberRegistry.getSubscribers` → `Dispatcher.dispatch` → only the first `Subscriber.dispatchEvent` → its executor → `Subscriber.invokeSubscriberMethod`. For e

### TMF_STALE
- Machine design score: 2
- Chain completeness: 0.80
- Source bytes read: 13995
- Human score (0/1/2): TBD
- Answer excerpt: The lost design property is **broadcast/fan-out delivery**: `EventBus.post` is specified to post an event to *all* registered matching subscribers, and the immediate dispatcher is intended only to alter dispatch ordering, independently of how each subscriber executes. `ImmediateDispatcher.dispatch` now consumes only the first iterator element, so delivery depends on iterator/registration order and all later matching subscribers silently miss the event.  The skipped downstream chain is: `EventBus.post` → `ImmediateDispatcher.dispatch` → each remaining `Subscriber.dispatchEvent` → that subscriber’s `Executor.execute` → `Subscriber.invokeSubscriberMethod`; consequently, later subscribers also n

### TMF_FRESH
- Machine design score: 2
- Chain completeness: 1.00
- Source bytes read: 16937
- Human score (0/1/2): TBD
- Answer excerpt: The change loses EventBus’s publish/subscribe broadcast fan-out property: `EventBus.post` obtains the immutable snapshot of all type-compatible subscribers from `SubscriberRegistry.getSubscribers` and passes that iterator to `Dispatcher.dispatch`; the ImmediateDispatcher is intended to exhaust it, not treat it as a first-consumer lookup. With first-match-only behavior, every subscriber after the first is skipped, so their downstream chain `Subscriber.dispatchEvent` -> executor scheduling -> `Subscriber.invokeSubscriberMethod` never runs. That breaks isolation/decoupling among independent subscribers because delivery to one subscriber now suppresses the others and makes behavior depend on ite

## B02

### SOURCE_ONLY
- Machine design score: 2
- Chain completeness: 1.00
- Source bytes read: 12456
- Human score (0/1/2): TBD
- Answer excerpt: The rename breaks every concrete `Dispatcher` implementation that still calls `Subscriber.dispatchEvent(Object)`: `PerThreadQueuedDispatcher.dispatch` while draining its per-thread queue, `LegacyAsyncDispatcher.dispatch` while draining its global `EventWithSubscriber` queue, and `ImmediateDispatcher.dispatch` while iterating subscribers. The concrete upstream chain is `EventBus.post` → `Dispatcher.dispatch` → one of those three implementations → the renamed `Subscriber.enqueueEventForDispatch` → `Executor.execute` → `Subscriber.invokeSubscriberMethod`; for subscribers not marked `@AllowConcurrentEvents`, virtual dispatch reaches `SynchronizedSubscriber.invokeSubscriberMethod`. The old `dispa

### TMF_STALE
- Machine design score: 2
- Chain completeness: 0.60
- Source bytes read: 10321
- Human score (0/1/2): TBD
- Answer excerpt: The rename breaks all three concrete `Dispatcher.dispatch(...)` implementations because they still call the now-nonexistent `Subscriber.dispatchEvent(...)`: `PerThreadQueuedDispatcher.dispatch(...)` at line 112, `LegacyAsyncDispatcher.dispatch(...)` at line 166, and `ImmediateDispatcher.dispatch(...)` at line 189. Consequently, the upstream posting chain `EventBus.post(...)` → `dispatcher.dispatch(event, eventSubscribers)` → one of those three implementations → `Subscriber.dispatchEvent(...)` no longer compiles; each terminal call must target `enqueueEventForDispatch(...)` instead.  The old `dispatchEvent` boundary enforced a deliberate separation between dispatch ordering and subscriber exe

### TMF_FRESH
- Machine design score: 2
- Chain completeness: 1.00
- Source bytes read: 14378
- Human score (0/1/2): TBD
- Answer excerpt: The broken direct callers are all three `Dispatcher` implementations, because each still invokes `Subscriber.dispatchEvent(...)`: `PerThreadQueuedDispatcher.dispatch` while draining its per-thread event queue, `LegacyAsyncDispatcher.dispatch` while draining its global event/subscriber queue, and `ImmediateDispatcher.dispatch` while iterating subscribers directly. After renaming that Subscriber method to `enqueueEventForDispatch`, these references no longer resolve, so every dispatcher mode is broken. Upstream, this breaks the normal chain `EventBus.post` → `Dispatcher.dispatch` for the default `perThreadDispatchQueue()` dispatcher, as well as users of `legacyAsync()` and `immediate()` (inclu

