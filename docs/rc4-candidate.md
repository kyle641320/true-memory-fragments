# 0.1.0rc4 candidate — unreleased

This candidate includes stale-slice relevance improvements, read-only locator compatibility and the legacy OpenClaw assist module adapter. It is not yet a tagged release or a PyPI publication.

## Upgrade contract

Release preflight runs the legacy locator and assist adapter regression suites. They cover legacy JSON claims, modern freshness version gates, external state refresh, service-local state isolation, read-only behavior, resource cleanup and bounded assist validation. Installed stdio smoke against a copied real legacy state is additional local evidence, not a substitute for live-client acceptance.

Keep the old repository path, external state and opt-in assist settings when testing the new package. The nine legacy schemas remain supported; stale_slice is additive. Search ranking can change. Locator warm_complete remains conservatively false. Never automatically rebuild or migrate the user's state on a query.

The assist adapter's offline tests use a fake OpenClaw executable: they do not establish that the actual provider route is healthy. Source freshness is not a mandatory write gate or automatic worktree routing.

## Rollout

Build and test a uniquely versioned wheel in isolation; keep the previous installation and configuration for rollback. Switch the live client only after its registration/reconnect path and real calls are verified. No gateway restart, live replacement, tag or package publication is performed by this candidate PR.

## Installed-artifact regression gate

Release preflight also runs `tools/verify_installed_upgrade.py` with the isolated
Java-extra wheel environment. It copies only the two upgrade test modules to a
fresh temporary directory, removes inherited Python/TMF configuration, and checks
that TMF imports from the venv site-packages before running the existing contracts.
This covers the shipped legacy CLI and assist module as well as JSON compatibility
and read-only behavior. It does not call a real assist provider or change a live
client. A missing module in the wheel must fail this gate even if source tests pass.
