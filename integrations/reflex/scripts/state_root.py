"""State adapter for frozen Store, which always appends .tmf to its root."""
from pathlib import Path


def canonical_state_root(repo_root, configured=None):
    state = (Path(configured).expanduser() if configured else Path(repo_root) / ".tmf").resolve()
    if state.name != ".tmf":
        raise ValueError("TMF state_root_error: stateRoot must resolve to a directory named .tmf")
    return state
