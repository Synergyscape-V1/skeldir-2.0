#!/usr/bin/env python3
"""Restore the pre-C20 write-clock allocation walk, for NC-C20-02 only.

Corrective XX, Exit Gate XX2-D's active falsifier needs the historical
behaviour back for exactly one pytest invocation: the bounded cardinality walk
over ``attribution_allocations`` bounded by its own ``created_at`` persistence
clock instead of the financial event clock the canonical SELECT admits it by.

This lives in a script rather than inline in the workflow because the mutation
must be exact and must fail loudly if the override is ever moved or renamed. A
heredoc that silently matched nothing would leave the negative control looking
like it fired when it had mutated nothing at all.
"""

from __future__ import annotations

import pathlib
import sys


TARGET = pathlib.Path("backend/app/bayesian/source_contract_authority.py")

OVERRIDE = """            walk_window_predicate=(
                "EXISTS (SELECT 1 FROM public.attribution_events AS window_event"
                " WHERE window_event.tenant_id = {alias}.tenant_id"
                " AND window_event.id = {alias}.event_id"
                " AND window_event.occurred_at >= :window_start"
                " AND window_event.occurred_at < :window_end)"
            ),
"""


def main() -> int:
    source = TARGET.read_text(encoding="utf-8")
    occurrences = source.count(OVERRIDE)
    if occurrences != 1:
        print(
            "NC-C20-02 cannot run: expected exactly one attribution_allocations"
            f" walk_window_predicate override, found {occurrences}."
            " The override was moved or rewritten; update this control before"
            " trusting the gate.",
            file=sys.stderr,
        )
        return 1
    TARGET.write_text(source.replace(OVERRIDE, "", 1), encoding="utf-8")
    print("NC-C20-02: allocation walk reverted to its write clock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
