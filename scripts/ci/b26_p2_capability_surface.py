#!/usr/bin/env python3
"""B2.6-P2 Corrective VI capability-derived authority-surface generator.

Mechanical inversion of the historical failure pattern (fixed named
defect lists as evidence of CLASS CLOSED). For each prohibited effect,
this generator constructs the machine-readable authority surface from
live catalog facts -- never from engineering vocabulary:

  pg_roles / pg_auth_members (recursive memberships)
  information_schema role_table_grants / role_column_grants /
    role_routine_grants (explicit + default-ACL-derived effective grants)
  pg_default_acl (ambient future grants)
  function ownership + SECURITY DEFINER writers (privilege-escalation
    surfaces: a DEFINER writer is an EXECUTE-to-write path)
  RLS policy graph (which principals read which projections)
  table constraints + triggers (which effects are already impossible)
  deployment processes (Procfile shipping commands -> runtime login)
  queue routing (which queue a process consumes)

Output: an effect-coverage manifest JSON:

  PROHIBITED EFFECT -> REACHABLE MUTATION SURFACES (role:priv:object)
  TESTED SURFACES (supplied by the caller -- the proof registers each
    falsifier's exercised surfaces)
  UNTESTED REACHABLE SURFACES (must be 0 for CLASS CLOSED)

CLASS CLOSED is forbidden while UNTESTED REACHABLE SURFACES > 0 for a
load-bearing effect. A new sibling grant/function/column that can
produce the prohibited effect appears here automatically: the proof
must either exercise it or fail coverage (Gate 29 active falsifier).

Usage:
  python scripts/ci/b26_p2_capability_surface.py \
    --dsn postgresql://postgres:postgres@127.0.0.1:5432/db \
    --manifest-out artifacts/b26_p2/topology/capability-surface.json \
    [--covered app_worker:INSERT:b26_p2_conduction_receipts ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Corrective XI: app_ingress is a runtime principal holding P2
# EXECUTE/table authority. It must be discovered like every other
# runtime role: undiscovered authority is ungoverned authority.
RUNTIME_ROLES = ("app_user", "app_worker", "app_relay", "app_beat", "app_ingress")

# Prohibited effect -> tables/columns whose mutation can produce it.
# Column sets are structural (every sovereign/bound column), not
# vocabulary: any future column added to these tables is automatically
# included via the wildcard pass below.
ROOT_TABLES = {
    "b23_match_task_dispatches": (
        "window_start",
        "window_end",
        "tenant_id",
        "webhook_ingress_identity_id",
        "provider",
        "task_name",
        "queue",
        "delivery_state",
    ),
    # VII complete sovereign-fact set (P2-CA7-02): clock/tenant/provider/
    # verified/currency/amount share one custody law.
    "webhook_ingress_identities": (
        "event_timestamp",
        "tenant_id",
        "provider",
        "verified_commerce_ingress_state",
        "verified_amount_currency",
        "verified_amount_minor",
    ),
    "b26_p2_task_authority_directory": (
        "window_start",
        "window_end",
        "tenant_id",
        "webhook_ingress_identity_id",
    ),
}

COMPLETION_TABLES = {
    "b26_p2_conduction_receipts": (
        "task_id",
        "tenant_id",
        "webhook_ingress_identity_id",
        "window_start",
        "window_end",
        "b23_processed_count",
        "p2_scope_identity",
    ),
    "b23_match_verdicts": ("status",),
    "b23_match_task_dispatches": ("delivery_state",),
    "b26_p2_execution_outbox": ("state",),
}

COMPLETION_ROUTINES = (
    "b26_p2_record_conduction_receipt",
    "b26_p2_mark_conducted",
)

DISPOSITION_TABLES = {
    "b23_match_task_dispatches": (
        "delivery_state",
        "publish_attempts",
        "last_publish_error",
        "updated_at",
        "first_published_at",
        "dispatched_at",
    ),
    "b26_p2_execution_outbox": (
        "state",
        "publish_attempts",
        "last_publish_error",
        "next_retry_at",
        "updated_at",
    ),
    "b26_p2_execution_quarantine": ("tenant_id", "reason"),
    "celery_taskmeta": ("status",),
    "worker_failed_jobs": ("status", "task_id"),
    # VII heartbeat (P2-CA7-06): evaluator writes, API reads.
    "b26_p2_evaluator_heartbeat": ("tenant_id", "last_tick"),
}

DISPOSITION_ROUTINES = (
    "b26_p2_stale_unconducted",
    "b26_p2_operational_disposition",
    "b26_p2_record_evaluator_heartbeat",
)

ROOT_ROUTINES = (
    "b26_p2_resolve_dispatch_authority",
)

# Pure-computation oracles: IMMUTABLE, no table access, no RLS
# interaction. EXECUTE on these cannot mutate any effect (they are the
# independent verification instruments, not authority surfaces), so
# they are excluded from mutation coverage by construction. Any routine
# that WRITES (DEFINER writers below) or GATES (resolver/gate/record)
# or parameterizes a signal (stale/disposition threshold) stays covered.
PURE_ORACLES = frozenset(
    {
        "b26_p2_canonical_day_start",
        "b26_p2_canonical_day_end",
    }
)


def _connect(dsn: str):
    import psycopg2

    return psycopg2.connect(dsn)


def _role_closure(cur) -> dict[str, set[str]]:
    """Transitive role membership: role -> set of roles it inherits."""
    cur.execute(
        "SELECT r.rolname, m.rolname FROM pg_auth_members "
        "JOIN pg_roles r ON r.oid = member "
        "JOIN pg_roles m ON m.oid = roleid"
    )
    direct: dict[str, set[str]] = {}
    for member, parent in cur.fetchall():
        direct.setdefault(member, set()).add(parent)
    closure: dict[str, set[str]] = {}

    def _expand(role: str, seen: set[str]) -> set[str]:
        if role in closure:
            return closure[role]
        out: set[str] = set()
        for parent in direct.get(role, ()):
            if parent not in seen:
                out.add(parent)
                out |= _expand(parent, seen | {parent})
        closure[role] = out
        return out

    for role in RUNTIME_ROLES:
        _expand(role, {role})
    return closure


def _effective_table_privs(cur) -> list[tuple[str, str, str]]:
    """(grantee, table, priv) effective rows for runtime roles (direct + inherited)."""
    cur.execute(
        """
        SELECT grantee, table_name, privilege_type
        FROM information_schema.role_table_grants
        WHERE table_schema = 'public'
          AND grantee IN ('app_user', 'app_worker', 'app_rw', 'app_ro',
                          'app_relay', 'app_beat', 'PUBLIC')
        """
    )
    return [(str(a), str(b), str(c)) for a, b, c in cur.fetchall()]


def _effective_column_privs(cur) -> list[tuple[str, str, str, str]]:
    cur.execute(
        """
        SELECT grantee, table_name, column_name, privilege_type
        FROM information_schema.role_column_grants
        WHERE table_schema = 'public'
        """
    )
    return [(str(a), str(b), str(c), str(d)) for a, b, c, d in cur.fetchall()]


def _effective_routine_privs(cur) -> list[tuple[str, str, str]]:
    cur.execute(
        """
        SELECT grantee, routine_name, privilege_type
        FROM information_schema.role_routine_grants
        WHERE routine_schema = 'public'
        """
    )
    return [(str(a), str(b), str(c)) for a, b, c in cur.fetchall()]


def _definer_writers(cur) -> list[tuple[str, str]]:
    """SECURITY DEFINER functions that write P2 tables: (function, table)."""
    cur.execute(
        """
        SELECT p.proname, c.relname
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_depend d ON d.objid = p.oid AND d.deptype = 'n'
        JOIN pg_class c ON c.oid = d.refobjid
        WHERE n.nspname = 'public' AND p.prosecdef
          AND c.relnamespace = 'public'::regnamespace
          AND c.relname LIKE 'b2%\_p2\_%' ESCAPE '\\'
        """
    )
    rows = [(str(a), str(b)) for a, b in cur.fetchall()]
    # pg_depend text search misses dynamic SQL writers; the governed
    # DEFINER set is small and enumerated explicitly as a backstop, with
    # each entry verified against pg_proc.prosecdef below.
    cur.execute(
        "SELECT proname FROM pg_proc WHERE prosecdef AND pronamespace='public'::regnamespace"
    )
    definers = {str(r[0]) for r in cur.fetchall()}
    backstop = [
        ("b26_p2_mark_conducted", "b23_match_task_dispatches"),
        ("b26_p2_mark_conducted", "b26_p2_execution_outbox"),
        ("b26_p2_record_conduction_receipt", "b26_p2_conduction_receipts"),
    ]
    for fn, tbl in backstop:
        if fn in definers and (fn, tbl) not in rows:
            rows.append((fn, tbl))
    return sorted(set(rows))


def _default_acls(cur) -> list[str]:
    cur.execute(
        """
        SELECT pg_get_userbyid(d.defaclrole) || ':' || COALESCE(d.defaclacl::text, '')
        FROM pg_default_acl d JOIN pg_namespace n ON n.oid = d.defaclnamespace
        WHERE n.nspname = 'public'
        """
    )
    return sorted(str(r[0]) for r in cur.fetchall())


def _surfaces_for(
    table_map: dict[str, tuple[str, ...]],
    table_privs: list[tuple[str, str, str]],
    column_privs: list[tuple[str, str, str, str]],
    closure: dict[str, set[str]],
    kinds: tuple[str, ...] = ("INSERT", "UPDATE"),
) -> list[str]:
    """Reachable role:priv:table[.column] surfaces, membership-expanded.

    A role reaches a grant held by any role it inherits (plus PUBLIC).
    Column-level UPDATE grants expand to their exact columns; table-level
    UPDATE expands to every governed column of that table (a table-wide
    UPDATE can mutate any column the trigger does not freeze -- and the
    trigger freeze is a SEPARATE defense verified by its own falsifier,
    never assumed here).
    """
    surfaces: set[str] = set()
    for role in RUNTIME_ROLES:
        effective = {role} | closure.get(role, set()) | {"PUBLIC"}
        for grantee, table, priv in table_privs:
            if grantee not in effective or priv not in kinds:
                continue
            if table not in table_map:
                continue
            if priv == "INSERT":
                surfaces.add(f"{role}:{priv}:{table}")
            else:
                for col in table_map[table]:
                    surfaces.add(f"{role}:{priv}:{table}.{col}")
        for grantee, table, col, priv in column_privs:
            if grantee not in effective or priv not in kinds:
                continue
            if table not in table_map or col not in table_map[table]:
                continue
            surfaces.add(f"{role}:{priv}:{table}.{col}")
    return sorted(surfaces)


def _routine_surfaces(
    routines: tuple[str, ...],
    routine_privs: list[tuple[str, str, str]],
    closure: dict[str, set[str]],
) -> list[str]:
    surfaces: set[str] = set()
    for role in RUNTIME_ROLES:
        effective = {role} | closure.get(role, set()) | {"PUBLIC"}
        for grantee, routine, priv in routine_privs:
            if grantee not in effective or priv != "EXECUTE":
                continue
            if routine in PURE_ORACLES:
                continue
            if routine in routines:
                surfaces.add(f"{role}:EXECUTE:{routine}")
    return sorted(surfaces)


def _all_runtime_definers(cur) -> list[tuple[str, str]]:
    """Open-world SECURITY DEFINER inventory (VII, §13.1/13.3/13.5).

    Enumerates EVERY SECURITY DEFINER routine in public + its EXECUTE
    grantees (direct + inherited + PUBLIC), without filtering by known
    P2 names and without relying on pg_depend body tracking (blind for
    plpgsql bodies). A new definer executable by a runtime principal
    appears here automatically; classification happens AFTER discovery.
    """
    cur.execute(
        """
        SELECT p.proname
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prosecdef
        ORDER BY 1
        """
    )
    definers = [str(r[0]) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT grantee, routine_name
        FROM information_schema.role_routine_grants
        WHERE routine_schema = 'public' AND privilege_type = 'EXECUTE'
        """
    )
    grants = [(str(a), str(b)) for a, b in cur.fetchall()]
    out: list[tuple[str, str]] = []
    closure = _role_closure(cur)
    for role in RUNTIME_ROLES:
        effective = {role} | closure.get(role, set()) | {"PUBLIC"}
        for grantee, routine in grants:
            if grantee in effective and routine in definers:
                out.append((routine, role))
    return sorted(set(out))


def _all_runtime_definers(cur) -> list[tuple[str, str]]:
    """Open-world SECURITY DEFINER inventory (VII, §13.1/13.3/13.5).

    Enumerates EVERY SECURITY DEFINER routine in public + its EXECUTE
    grantees (direct + inherited + PUBLIC), without filtering by known
    P2 names and without relying on pg_depend body tracking (blind for
    plpgsql bodies). A new definer executable by a runtime principal
    appears here automatically; classification happens AFTER discovery.
    """
    cur.execute(
        """
        SELECT p.proname
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prosecdef
        ORDER BY 1
        """
    )
    definers = [str(r[0]) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT grantee, routine_name
        FROM information_schema.role_routine_grants
        WHERE routine_schema = 'public' AND privilege_type = 'EXECUTE'
        """
    )
    grants = [(str(a), str(b)) for a, b in cur.fetchall()]
    out: list[tuple[str, str]] = []
    closure = _role_closure(cur)
    for role in RUNTIME_ROLES:
        effective = {role} | closure.get(role, set()) | {"PUBLIC"}
        for grantee, routine in grants:
            if grantee in effective and routine in definers:
                out.append((routine, role))
    return sorted(set(out))


# Corrective VIII meaning-bearing discovery (§12). The VII denominator
# binds grant/name membership only; a same-name body mutation, an
# overload, a trigger-mediated writer, or a schema-CREATE grant leaves
# every VII surface unchanged while effective authority meaning changes.
# Every helper below observes MEANING from pg_catalog, never from
# engineering vocabulary. Unknown = RED via the universe pin + the
# unclassified-meaning census (see build_manifest).
MEANING_TABLES = (
    "webhook_ingress_identities",
    "b23_match_task_dispatches",
    "b23_match_verdicts",
    "b26_p2_execution_outbox",
    "b26_p2_task_authority_directory",
    "b26_p2_conduction_receipts",
    "b26_p2_execution_quarantine",
    "b26_p2_scope_policy_authority",
    "b26_p2_evaluator_heartbeat",
)


def _routine_meaning_identities(cur) -> list[str]:
    """Meaning identity of project-authority routines: signature + owner +
    secdef flag + search_path config + body digest (not bare name).

    Scope is principled, not convenient: a SECURITY INVOKER routine owned
    by the platform superuser executes with the CALLER's privileges, so it
    confers no authority the caller lacks (the caller's grant surfaces,
    inventoried separately, already govern those writes). The escalation
    primitives — SECURITY DEFINER, trigger mediation, ownership/CREATE —
    are each censused in full. Platform postgres-owned non-secdef
    builtins (which vary across server versions, e.g. fips_mode on
    pg18) therefore cannot silently move the reviewed identity, while every
    project-owned or privilege-escalating routine is bound.
    """
    import hashlib as _hashlib

    cur.execute(
        """
        SELECT p.proname,
               pg_get_function_identity_arguments(p.oid),
               pg_get_userbyid(p.proowner),
               p.prosecdef,
               COALESCE(p.proconfig::text, ''),
               COALESCE(p.prosrc, '')
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND (p.prosecdef OR pg_get_userbyid(p.proowner) <> 'postgres')
        ORDER BY 1, 2
        """
    )
    out: list[str] = []
    for name, args, owner, secdef, config, src in cur.fetchall():
        body = _hashlib.sha256(str(src).encode("utf-8")).hexdigest()
        out.append(
            f"{name}({args})|owner={owner}|secdef={bool(secdef)}"
            f"|config={config}|body={body}"
        )
    return sorted(out)


def _trigger_meaning_census(cur) -> list[str]:
    """Every non-internal trigger on meaning-bearing tables + the
    trigger function's owner and body digest (trigger-mediated writers
    cannot hide behind a lawful table operation)."""
    import hashlib as _hashlib

    cur.execute(
        """
        SELECT c.relname, t.tgname, p.proname,
               pg_get_userbyid(p.proowner),
               COALESCE(p.prosrc, ''),
               (t.tgenabled <> 'D')
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_proc p ON p.oid = t.tgfoid
        WHERE c.relnamespace = 'public'::regnamespace
          AND c.relname IN ('webhook_ingress_identities',
                            'b23_match_task_dispatches',
                            'b23_match_verdicts',
                            'b26_p2_execution_outbox',
                            'b26_p2_task_authority_directory',
                            'b26_p2_conduction_receipts',
                            'b26_p2_execution_quarantine',
                            'b26_p2_scope_policy_authority',
                            'b26_p2_evaluator_heartbeat')
          AND NOT t.tgisinternal
        ORDER BY 1, 2
        """
    )
    out: list[str] = []
    for rel, tg, fn, owner, src, enabled in cur.fetchall():
        body = _hashlib.sha256(str(src).encode("utf-8")).hexdigest()
        out.append(
            f"{rel}.{tg}->{fn}|owner={owner}|body={body}|enabled={bool(enabled)}"
        )
    return sorted(out)


def _schema_meaning_privs(cur) -> list[str]:
    """Schema USAGE/CREATE reachable by runtime roles (ownership of a
    searched schema is authority to create future behavior)."""
    per_role: list[str] = []
    for role in RUNTIME_ROLES:
        cur.execute(
            "SELECT has_schema_privilege(%s, 'public', 'USAGE'),"
            " has_schema_privilege(%s, 'public', 'CREATE')",
            (role, role),
        )
        usage, create = cur.fetchone()
        per_role.append(
            f"{role}:schema=public|USAGE={bool(usage)}|CREATE={bool(create)}"
        )
    return sorted(set(per_role))


def _rls_meaning_census(cur) -> list[str]:
    """RLS/FORCE state + full policy definitions on meaning tables."""
    cur.execute(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c
        WHERE c.relnamespace = 'public'::regnamespace
          AND c.relname IN ('webhook_ingress_identities',
                            'b23_match_task_dispatches',
                            'b23_match_verdicts',
                            'b26_p2_execution_outbox',
                            'b26_p2_task_authority_directory',
                            'b26_p2_conduction_receipts',
                            'b26_p2_execution_quarantine',
                            'b26_p2_scope_policy_authority',
                            'b26_p2_evaluator_heartbeat')
        ORDER BY 1
        """
    )
    flags = [
        f"{rel}|rls={bool(en)}|force={bool(fc)}" for rel, en, fc in cur.fetchall()
    ]
    cur.execute(
        """
        SELECT tablename, policyname, roles::text, cmd, qual, with_check
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN ('webhook_ingress_identities',
                            'b23_match_task_dispatches',
                            'b23_match_verdicts',
                            'b26_p2_execution_outbox',
                            'b26_p2_task_authority_directory',
                            'b26_p2_conduction_receipts',
                            'b26_p2_execution_quarantine',
                            'b26_p2_scope_policy_authority',
                            'b26_p2_evaluator_heartbeat')
        ORDER BY 1, 2
        """
    )
    policies = [
        f"{t}.{p}|roles={r}|cmd={c}|qual={q}|check={w}"
        for t, p, r, c, q, w in cur.fetchall()
    ]
    return sorted(flags + policies)


def _ownership_census(cur) -> list[str]:
    """Owners of meaning-bearing tables and routines (runtime ownership
    of a load-bearing object is future authority)."""
    cur.execute(
        """
        SELECT c.relname, pg_get_userbyid(c.relowner)
        FROM pg_class c
        WHERE c.relnamespace = 'public'::regnamespace
          AND c.relname IN ('webhook_ingress_identities',
                            'b23_match_task_dispatches',
                            'b23_match_verdicts',
                            'b26_p2_execution_outbox',
                            'b26_p2_task_authority_directory',
                            'b26_p2_conduction_receipts',
                            'b26_p2_execution_quarantine',
                            'b26_p2_scope_policy_authority',
                            'b26_p2_evaluator_heartbeat')
        ORDER BY 1
        """
    )
    tables = [f"table:{t}|owner={o}" for t, o in cur.fetchall()]
    cur.execute(
        """
        SELECT p.proname, pg_get_function_identity_arguments(p.oid),
               pg_get_userbyid(p.proowner)
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND (p.proname LIKE 'b26\\_p2\\_%' ESCAPE '\\'
               OR p.proname LIKE 'b24\\_%' ESCAPE '\\')
        ORDER BY 1, 2
        """
    )
    routines = [f"routine:{n}({a})|owner={o}" for n, a, o in cur.fetchall()]
    return sorted(tables + routines)


def _platform_invoker_routines(cur) -> frozenset[str]:
    """Platform-owned non-escalating routines (excluded from the reviewed
    denominator with justification).

    A SECURITY INVOKER routine owned by the platform superuser executes
    with the CALLER's privileges: it confers no authority the caller
    lacks, so its presence/absence cannot change any prohibited effect
    (the caller's grant surfaces, inventoried separately, already govern
    those writes). They are also server-version-sensitive (e.g.
    fips_mode exists on pg18, not pg15) and would otherwise make the
    reviewed identity a function of the platform version rather than of
    project authority. SECURITY DEFINER platform routines stay inventoried
    (escalation-relevant); project-owned routines stay bound by meaning.
    """
    cur.execute(
        """
        SELECT p.proname
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND NOT p.prosecdef
          AND pg_get_userbyid(p.proowner) = 'postgres'
        """
    )
    return frozenset(str(r[0]) for r in cur.fetchall())


def _discover_all_reachable(
    table_privs: list[tuple[str, str, str]],
    column_privs: list[tuple[str, str, str, str]],
    routine_privs: list[tuple[str, str, str]],
    closure: dict[str, set[str]],
    platform_invokers: frozenset[str] = frozenset(),
) -> list[str]:
    """Whole runtime-reachable authority universe BEFORE P2 filtering.

    Every role:priv:object reachable by a runtime principal (direct +
    inherited + PUBLIC) across ALL public tables/columns/routines, minus
    platform-owned non-escalating invoker routines (see
    _platform_invoker_routines: they confer no authority and are
    server-version-sensitive). Unknown is not ignored; classification
    happens after this census.
    """
    surfaces: set[str] = set()
    for role in RUNTIME_ROLES:
        effective = {role} | closure.get(role, set()) | {"PUBLIC"}
        for grantee, table, priv in table_privs:
            if grantee not in effective:
                continue
            if priv not in ("INSERT", "UPDATE", "SELECT", "DELETE"):
                continue
            surfaces.add(f"{role}:{priv}:{table}")
        for grantee, table, col, priv in column_privs:
            if grantee not in effective:
                continue
            if priv not in ("INSERT", "UPDATE", "SELECT"):
                continue
            surfaces.add(f"{role}:{priv}:{table}.{col}")
        for grantee, routine, priv in routine_privs:
            if grantee not in effective or priv != "EXECUTE":
                continue
            if routine in PURE_ORACLES:
                continue
            if routine in platform_invokers:
                continue
            surfaces.add(f"{role}:EXECUTE:{routine}")
    return sorted(surfaces)


# VII open-world allowlist (classification AFTER discovery, §13.2).
# Every runtime-executable SECURITY DEFINER known on the VII baseline is
# listed here with its authority family. A newly created definer executable
# by a runtime principal is absent from BOTH the P2 covered set AND this
# allowlist, so it appears as UNCLASSIFIED_RUNTIME_AUTHORITY and REDs.
# Do NOT extend this list to silence a new P2-reachable writer without a
# falsifier; that relabels a load-bearing defect as debt.
KNOWN_NON_P2_DEFINERS = frozenset(
    {
        "b24_claim_fit_dispatch",
        "b24_complete_fit_dispatch",
        "b24_complete_fit_planner_wakeup",
        "b24_create_fit_recovery_wakeups",
        "b24_current_dispatch_fence_valid",
        "b24_due_fit_planner_tenants",
        "b24_enforce_c11_policy_provenance",
        "b24_enforce_dispatch_fence",
        "b24_fail_fit_dispatch_recoverable",
        "b24_fail_fit_dispatch_terminal",
        "b24_fit_planner_residual_obligation",
        "b24_invalidate_attribution_allocations_delete",
        "b24_invalidate_attribution_allocations_insert",
        "b24_invalidate_attribution_allocations_update",
        "b24_invalidate_attribution_events_delete",
        "b24_invalidate_attribution_events_insert",
        "b24_invalidate_attribution_events_update",
        "b24_invalidate_b23_match_verdicts_delete",
        "b24_invalidate_b23_match_verdicts_insert",
        "b24_invalidate_b23_match_verdicts_update",
        "b24_invalidate_b23_revenue_events_delete",
        "b24_invalidate_b23_revenue_events_insert",
        "b24_invalidate_b23_revenue_events_update",
        "b24_lease_fit_recovery_rows",
        "b24_mark_allocation_financial_window_dirty",
        "b24_mark_fit_dispatch_running",
        "b24_mark_fit_recovery_failed",
        "b24_mark_fit_recovery_published",
        "b24_mark_verdict_financial_window_dirty",
        "b24_next_active_worker_generation",
        "b24_register_worker_process_authority",
        "b24_signal_fit_planner_wakeup",
        "b24_signal_fit_planner_wakeup_coalesced",
        "b27_supersede_stale_explanations",
        "b28_authenticate_request_possession",
        "fn_b23_p0_prune_attribution_commerce_identities",
        "fn_b23_p0_prune_attribution_commerce_identities_trigger",
        "fn_b23_p1_apply_lifecycle",
        "fn_log_channel_assignment_correction",
        "fn_log_channel_state_change",
        "fn_log_revenue_state_change",
        "skeldir_database_construction_revisions",
    }
)

KNOWN_P2_DEFINERS = frozenset(
    {
        # Corrective X: the provenance attester is a new SECURITY
        # DEFINER authority (census-visible). Corrective XI moves its
        # EXECUTE to app_ingress alone (ordinary app_user revoked).
        # The effect guards are SECURITY DEFINER with no EXECUTE
        # grant to any role (they fire through triggers only, proven
        # live): they are tracked by the X authority validator (live
        # source equivalence) and the bootstrap trigger census, never
        # by the grant-based definer census. (The normalization
        # family, the strip helpers, and the classifier are SECURITY
        # INVOKER pure computation: EXECUTE surface census + X coverage
        # registry.)
        "b26_p2_attest_provenance_evidence",
        "b26_p2_canonical_scope_identity_for_window",
        "b26_p2_mark_conducted",
        "b26_p2_operational_disposition",
        "b26_p2_record_conduction_receipt",
        "b26_p2_record_evaluator_heartbeat",
        "b26_p2_record_scheduler_heartbeat",
        "b26_p2_resolve_dispatch_authority",
        "b26_p2_stale_unconducted",
        # Corrective XI: the authentication witness recorder (EXECUTE
        # app_ingress alone; the witness table takes no runtime
        # INSERT) and the read-only P3 eligibility predicate
        # (EXECUTE runtime roles; mints nothing). Both are
        # P2-covered (b26_p2_xi_coverage) and falsified by the XI
        # battery (XA/XB/XE cells) plus the XI live validators. (The
        # XI invariant oracle and the quarantine-exclusion guard fire
        # with no runtime EXECUTE, like the X effect guards: tracked
        # by the XI census validator and the bootstrap routine
        # census, never by the grant-based definer census.)
        "b26_p2_record_ingress_auth_witness",
        "b26_p2_state_eligible_for_p3",
        # Corrective XII: the predecessor-event recorder (EXECUTE
        # app_user alone; the ingress principal cannot author P) and
        # the read-only topology adjudicator (EXECUTE runtime roles;
        # mints nothing). Both are P2-covered (b26_p2_xii_coverage)
        # and falsified by the XII battery (AUTH/TOPO cells) plus the
        # XII live validators. (The XII provision function and the
        # XII oracle grant no runtime EXECUTE, like the X effect
        # guards: tracked by the XII topology validator and the
        # bootstrap routine census, never by the grant census.)
        "b26_p2_record_provider_auth_consequence",
        "b26_p2_xii_topology_check",
    }
)


def build_manifest(dsn: str, covered: tuple[str, ...]) -> dict:
    conn = _connect(dsn)
    try:
        cur = conn.cursor()
        closure = _role_closure(cur)
        table_privs = _effective_table_privs(cur)
        column_privs = _effective_column_privs(cur)
        routine_privs = _effective_routine_privs(cur)
        definers = _definer_writers(cur)
        defaults = _default_acls(cur)
        all_definers = _all_runtime_definers(cur)
        platform_invokers = _platform_invoker_routines(cur)
        discovered_all = _discover_all_reachable(
            table_privs, column_privs, routine_privs, closure,
            platform_invokers,
        )
        # Corrective VIII meaning-bearing discovery (independent planes).
        routine_meaning = _routine_meaning_identities(cur)
        trigger_meaning = _trigger_meaning_census(cur)
        schema_meaning = _schema_meaning_privs(cur)
        rls_meaning = _rls_meaning_census(cur)
        ownership = _ownership_census(cur)
    finally:
        conn.close()
    covered_set = set(covered)
    effects: dict[str, dict] = {}
    for name, tables, routines in (
        ("forged_canonical_root", ROOT_TABLES, ROOT_ROUTINES),
        ("false_conducted", COMPLETION_TABLES, COMPLETION_ROUTINES),
        ("stale_suppression", DISPOSITION_TABLES, DISPOSITION_ROUTINES),
    ):
        reachable = _surfaces_for(tables, table_privs, column_privs, closure)
        reachable += _routine_surfaces(routines, routine_privs, closure)
        reachable = sorted(set(reachable))
        tested = sorted(s for s in reachable if s in covered_set)
        untested = sorted(s for s in reachable if s not in covered_set)
        effects[name] = {
            "reachable_surfaces": reachable,
            "tested_surfaces": tested,
            "untested_reachable_surfaces": untested,
        }
    # Quarantine/silent-graveyard effect: writers + readers per principal.
    quar_write = _surfaces_for(
        {"b26_p2_execution_quarantine": ("tenant_id", "reason")},
        table_privs,
        column_privs,
        closure,
    )
    quar_read = sorted(
        {
            f"{role}:SELECT:b26_p2_execution_quarantine"
            for role in RUNTIME_ROLES
            for (g, t, p) in table_privs
            if t == "b26_p2_execution_quarantine"
            and p == "SELECT"
            and g in ({role} | closure.get(role, set()) | {"PUBLIC"})
        }
    )
    effects["silent_quarantine"] = {
        "reachable_surfaces": sorted(set(quar_write + quar_read)),
        "tested_surfaces": sorted(
            s for s in set(quar_write + quar_read) if s in covered_set
        ),
        "untested_reachable_surfaces": sorted(
            s for s in set(quar_write + quar_read) if s not in covered_set
        ),
    }
    # Open-world authority census (VII §13): every runtime-executable
    # DEFINER must be either P2-covered or allowlisted non-P2. Unknown is
    # RED until classified (fail-closed, never omitted).
    open_world_unknown: list[str] = []
    for routine, role in all_definers:
        if routine in KNOWN_P2_DEFINERS:
            surface = f"{role}:EXECUTE:{routine}"
            if surface not in covered_set:
                open_world_unknown.append(f"UNCLASSIFIED_P2_DEFINER:{surface}")
        elif routine in KNOWN_NON_P2_DEFINERS:
            continue
        else:
            open_world_unknown.append(
                f"UNCLASSIFIED_RUNTIME_AUTHORITY:{role}:EXECUTE:{routine}"
            )
    open_world_unknown = sorted(set(open_world_unknown))
    effects["open_world_authority"] = {
        "reachable_surfaces": sorted(f"{r}:EXECUTE:{d}" for d, r in all_definers),
        "tested_surfaces": sorted(
            s
            for s in (f"{r}:EXECUTE:{d}" for d, r in all_definers)
            if s in covered_set or s.split(":")[-1] in KNOWN_NON_P2_DEFINERS
        ),
        "untested_reachable_surfaces": open_world_unknown,
    }
    # Authority manifest identity (VII §13.6 + VIII §12.6): normalized
    # hash of the live runtime authority universe. VIII binds MEANING,
    # not membership: routine signature/owner/secdef/config/body,
    # trigger identity/definition, schema privileges, RLS definitions,
    # and ownership. Any load-bearing semantic mutation changes this
    # identity; the reviewed pin (see assert_b26_p2_authority_universe)
    # turns that change into a RED until re-reviewed.
    import hashlib as _hashlib
    import json as _json

    universe_hash = _hashlib.sha256(
        _json.dumps(
            {
                "discovered": discovered_all,
                "definers": sorted(f"{d}:{r}" for d, r in all_definers),
                "defaults": defaults,
                "routine_meaning": routine_meaning,
                "trigger_meaning": trigger_meaning,
                "schema_meaning": schema_meaning,
                "rls_meaning": rls_meaning,
                "ownership": ownership,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    # Overload/meaning census: every allowlisted non-P2 name observed
    # with more than one live signature, owner, or body is reported for
    # explicit adjudication (same-name overloads cannot hide behind the
    # bare-name allowlist).
    import re as _re

    _sig_by_name: dict[str, set[str]] = {}
    for entry in routine_meaning:
        m = _re.match(r"([^\(]+)\(([^\)]*)\)\|owner=([^\|]+)\|", entry)
        if m:
            _sig_by_name.setdefault(m.group(1), set()).add(
                f"{m.group(2)}|{m.group(3)}"
            )
    multi_signature_names = sorted(
        n for n, sigs in _sig_by_name.items() if len(sigs) > 1
    )
    manifest = {
        "producer": "b26_p2_capability_surface",
        "effects": effects,
        "definer_writers": [f"{a}->{b}" for a, b in definers],
        "all_runtime_definers": [f"{a}:{b}" for a, b in all_definers],
        "discovered_runtime_authority_count": len(discovered_all),
        "authority_universe_hash": universe_hash,
        "open_world_unknown": open_world_unknown,
        "default_acls": defaults,
        "routine_meaning_identities": routine_meaning,
        "trigger_meaning_census": trigger_meaning,
        "schema_meaning_privs": schema_meaning,
        "rls_meaning_census": rls_meaning,
        "ownership_census": ownership,
        "multi_signature_routine_names": multi_signature_names,
        "class_closed": all(
            len(e["untested_reachable_surfaces"]) == 0 for e in effects.values()
        ),
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--manifest-out", type=Path, default=None)
    parser.add_argument("--covered", nargs="*", default=[])
    parser.add_argument("--fail-on-untested", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest(args.dsn, tuple(args.covered))
    total_untested = sum(
        len(e["untested_reachable_surfaces"]) for e in manifest["effects"].values()
    )
    if args.manifest_out is not None:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for name, effect in manifest["effects"].items():
        print(
            f"effect={name} reachable={len(effect['reachable_surfaces'])} "
            f"tested={len(effect['tested_surfaces'])} "
            f"untested={len(effect['untested_reachable_surfaces'])}"
        )
        for surface in effect["untested_reachable_surfaces"][:25]:
            print(f"  UNTESTED: {surface}")
    if args.fail_on_untested and total_untested > 0:
        print(f"B26_P2_CAPABILITY_COVERAGE_FAIL untested={total_untested}")
        return 1
    print(
        "B26_P2_CAPABILITY_COVERAGE_PASS"
        if total_untested == 0
        else f"B26_P2_CAPABILITY_COVERAGE_OPEN untested={total_untested}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
