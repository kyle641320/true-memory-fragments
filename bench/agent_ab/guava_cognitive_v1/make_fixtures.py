#!/usr/bin/env python3
"""Generate task variants for guava_cognitive_v1 from the pristine base copies.

Design constraints:
  * Never touch TMF engine code. This script only writes under fixtures/.
  * Every mutation is a string replacement whose target snippet was verified
    unique inside its file. Uniqueness is re-asserted at generation time, so a
    future Guava source refresh fails loudly instead of silently mutating the
    wrong line.
  * base/ stays pristine. Variants are written to sibling directories
    (work/ for agent-editable trees, mutated/ for read-only reasoning inputs).

Usage:
    python3 make_fixtures.py            # generate all
    python3 make_fixtures.py --check    # verify anchors only, write nothing
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

SUITE = Path(__file__).resolve().parent
FIXTURES = SUITE / "fixtures"
PKG_DIR = "com/google/common/eventbus"


class AnchorError(RuntimeError):
    """Raised when a mutation anchor is missing or ambiguous."""


@dataclass
class Mutation:
    file: str
    find: str
    replace: str

    def apply(self, root: Path) -> None:
        target = root / self.file
        if not target.is_file():
            raise AnchorError(f"missing file: {target}")
        text = target.read_text(encoding="utf-8")
        count = text.count(self.find)
        if count != 1:
            raise AnchorError(
                f"anchor not unique in {self.file}: found {count} occurrences of "
                f"{self.find!r} (expected exactly 1)"
            )
        target.write_text(text.replace(self.find, self.replace), encoding="utf-8")


@dataclass
class Variant:
    """One generated tree for a task."""

    name: str  # subdirectory under fixtures/<task>/
    mutations: list[Mutation] = field(default_factory=list)
    note: str = ""


@dataclass
class TaskFixture:
    task: str
    variants: list[Variant]


# ---------------------------------------------------------------------------
# Mutation definitions. Snippets below were each confirmed to appear exactly
# once in the corresponding base file before being encoded here.
# ---------------------------------------------------------------------------

B02_SIGNATURE = Mutation(
    file="SubscriberRegistry.java",
    find="  Iterator<Subscriber> getSubscribers(Object event) {",
    replace="  List<Subscriber> getSubscribers(Object event) {",
)

# The body currently ends with `return concat(subscriberIterators.iterator());`
# which no longer type-checks once the signature returns a List. Flattening it
# here keeps the *declared* contract the agent must preserve, and leaves the
# compile break where the task intends it: at the caller in EventBus.post.
B02_BODY = Mutation(
    file="SubscriberRegistry.java",
    find="    return concat(subscriberIterators.iterator());",
    replace="    return ImmutableList.copyOf(concat(subscriberIterators.iterator()));",
)

# No import mutation is required: base already imports ImmutableList (line 29),
# java.util.List (line 40), and statically imports Iterators.concat (line 19).
# Adding an import here produced a duplicate-import diff, so it was dropped.

B01_REMOVE_DEADEVENT = Mutation(
    file="EventBus.java",
    find="    } else if (!(event instanceof DeadEvent)) {",
    replace="    } else if (false) { // DeadEvent re-post branch disabled",
)


FIXTURE_PLAN: list[TaskFixture] = [
    # B01 is pure reasoning over the pristine tree. A mutated copy is generated
    # so the grader can diff intent, but the agent reasons about base/.
    TaskFixture(
        task="B01",
        variants=[
            Variant(
                name="mutated",
                mutations=[B01_REMOVE_DEADEVENT],
                note="reference-only: shows the edit the question asks about",
            ),
        ],
    ),
    # B02 is compile-repair: the agent edits work/ in place.
    TaskFixture(
        task="B02",
        variants=[
            Variant(
                name="work",
                mutations=[B02_SIGNATURE, B02_BODY],
                note="agent-editable tree; must compile after repair",
            ),
        ],
    ),
    # B03 reasons about the pristine async chain. No mutation needed.
    TaskFixture(task="B03", variants=[]),
]


def build(task: TaskFixture, *, check_only: bool) -> list[dict]:
    base = FIXTURES / task.task / "base"
    if not base.is_dir():
        raise AnchorError(f"missing base tree: {base}")

    records: list[dict] = []
    for variant in task.variants:
        dest = FIXTURES / task.task / variant.name
        if check_only:
            # Validate anchors against a scratch copy so nothing persists.
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                scratch = Path(tmp) / "base"
                shutil.copytree(base, scratch)
                for mutation in variant.mutations:
                    mutation.apply(scratch)
        else:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(base, dest)
            for mutation in variant.mutations:
                mutation.apply(dest)

        records.append(
            {
                "task": task.task,
                "variant": variant.name,
                "path": str(dest.relative_to(SUITE)),
                "mutations": [
                    {"file": m.file, "find": m.find} for m in variant.mutations
                ],
                "note": variant.note,
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify mutation anchors without writing fixtures",
    )
    args = parser.parse_args()

    all_records: list[dict] = []
    try:
        for task in FIXTURE_PLAN:
            all_records.extend(build(task, check_only=args.check))
    except AnchorError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    mode = "CHECK" if args.check else "GENERATED"
    for rec in all_records:
        muts = ", ".join(m["file"] for m in rec["mutations"]) or "(no mutation)"
        print(f"{mode}: {rec['task']}/{rec['variant']:<8} {muts}")

    if not args.check:
        manifest = SUITE / "fixtures" / "MANIFEST.json"
        manifest.write_text(
            json.dumps({"package_dir": PKG_DIR, "variants": all_records}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {manifest.relative_to(SUITE)}")

    print(f"OK: {len(all_records)} variant(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
