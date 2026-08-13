# Secure model broker
Operational daemon outside benchmark arms. `client.py` is the absolute executable for `JsonBrokerAdapter`; it forwards one newline-delimited JSON request over the Unix socket. The daemon pins `gpt-5.6-sol`, is stateless, exposes no tools/fallback, owns network/credential, and logs metadata/hash only.

A/B integration assets exist under `bench/agent_ab/java_real_v1`, including frozen `PROTOCOL.md`, `manifest.json`, and `runner.py`. This change supplies only the broker; it does not claim a new paired run because no isolated arm assignment/runtime invocation was requested or produced.
