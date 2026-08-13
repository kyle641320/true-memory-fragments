# Secure model broker
Operational daemon outside benchmark arms. `client.py` is the absolute executable for `JsonBrokerAdapter`; it forwards one newline-delimited JSON request over the Unix socket. The daemon pins `gpt-5.6-sol`, is stateless, exposes no tools/fallback, owns network/credential, and logs metadata/hash only.

The checked-in deployment defaults deliberately preserve this timeout hierarchy: experiment `120s` > client `100s` > upstream `90s`. This lets the broker return a bounded upstream timeout before the client or frozen experiment kills the request. Install `broker.py`, `client.py`, and `tmf-model-broker.service` into the paths named by the service, without copying environment files or credentials into the repository; then restart the service. `tests/test_model_broker.py` verifies the checked-in defaults and hierarchy.

A/B integration assets exist under `bench/agent_ab/java_real_v1`, including frozen `PROTOCOL.md`, `manifest.json`, and `runner.py`. This change supplies only the broker; it does not claim a new paired run because no isolated arm assignment/runtime invocation was requested or produced.
