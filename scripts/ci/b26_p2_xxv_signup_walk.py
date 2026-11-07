#!/usr/bin/env python3
"""Supported signup and single-membership login walk.

This walk creates every business through the shipped HTTP signup operation. It
does not seed an account, mint a token, use a CONTRACT_TESTING/TESTING bypass,
or inject an identity. The existing XXV lane supplies only the disposable
topology and unrelated control fixtures, which are disclosed and never used.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RESULT_PATH = (
    REPO
    / "docs/forensics/evidence/b26_p2_xxv_a8"
    / "xxv-r0039-signup-walk-20261107.json"
)
LOGIN_PEPPER = "xxv-login-pepper"


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _configure_lane() -> dict:
    tag = uuid.uuid4().hex[:8]
    prefix = f"b26p2xxvsignup{tag}"
    lane_root = Path(tempfile.gettempdir()) / f"{prefix}-lane"
    ports = {
        "pg": _free_port(),
        "api": _free_port(),
        "auth": _free_port(),
    }
    os.environ["B26_P2_XXV_PREFIX"] = prefix
    os.environ["B26_P2_XXV_DB"] = f"skeldir_signup_{tag}"
    os.environ["B26_P2_XXV_LANE_ROOT"] = str(lane_root)
    os.environ["B26_P2_XXV_PG_PORT"] = str(ports["pg"])
    os.environ["B26_P2_XXV_API_PORT"] = str(ports["api"])
    os.environ["B26_P2_XXV_AUTH_PORT"] = str(ports["auth"])
    return {
        "prefix": prefix,
        "lane_root": str(lane_root),
        "database": os.environ["B26_P2_XXV_DB"],
        "ports": ports,
    }


_LANE = _configure_lane()
os.environ.setdefault(
    "DATABASE_URL", "postgresql://fixture@127.0.0.1:1/fixture"
)
os.environ.setdefault("SKELDIR_CONTROL_PLANE_ENABLED", "0")
os.environ.setdefault("ENVIRONMENT", "ci")
os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "xxv-platform-key")
os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", "xxv-key")

sys.path.insert(0, str(REPO / "scripts" / "ci"))
sys.path.insert(0, str(REPO / "backend"))

from b26_p2_xxv_lane import (  # noqa: E402
    API_PORT,
    BOOTSTRAP_IMAGE,
    FINAL_IMAGE,
    LANE_ROOT,
    PREFIX,
    admin_dsn,
    cmd_down,
    cmd_up,
    docker,
    load_state,
    role_dsn,
    sql,
)
from app.services.auth_tokens import hash_login_identifier  # noqa: E402


def _now() -> str:
    from datetime import datetime, timezone  # noqa: PLC0415

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _http(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    token: str | None = None,
) -> tuple[int, dict | str]:
    headers = {"X-Correlation-ID": str(uuid.uuid4())}
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"http://127.0.0.1:{API_PORT}{path}",
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        return 0, f"transport_error:{type(exc).__name__}:{exc}"
    try:
        return status, json.loads(raw)
    except Exception:  # noqa: BLE001
        return status, raw


def _signup(
    email: str,
    password: str,
    workspace_name: str,
    *,
    extra: dict | None = None,
) -> tuple[int, dict | str]:
    body = {
        "email": email,
        "password": password,
        "workspace_name": workspace_name,
    }
    if extra:
        body.update(extra)
    return _http("POST", "/api/auth/signup", body=body)


def _login(
    email: str,
    password: str,
    *,
    tenant_id: str | None = None,
) -> tuple[int, dict | str]:
    body = {"email": email, "password": password}
    if tenant_id is not None:
        body["tenant_id"] = tenant_id
    return _http("POST", "/api/auth/login", body=body)


def _verify(access_token: str) -> tuple[int, dict | str]:
    return _http("GET", "/api/auth/verify", token=access_token)


def _hash(email: str) -> str:
    return hash_login_identifier(email, LOGIN_PEPPER)


def _user_count(email: str) -> int:
    return int(
        sql(
            "SELECT count(*) FROM public.users"
            " WHERE login_identifier_hash = %s",
            (_hash(email),),
        )[0][0]
    )


def _account_totals() -> dict[str, int]:
    return {
        "tenants": int(sql("SELECT count(*) FROM public.tenants")[0][0]),
        "users": int(sql("SELECT count(*) FROM public.users")[0][0]),
        "memberships": int(
            sql("SELECT count(*) FROM public.tenant_memberships")[0][0]
        ),
        "membership_roles": int(
            sql("SELECT count(*) FROM public.tenant_membership_roles")[0][0]
        ),
    }


def _tenant_count(name: str) -> int:
    return int(
        sql("SELECT count(*) FROM public.tenants WHERE name = %s", (name,))[0][0]
    )


def _account_rows(email: str) -> dict:
    user = sql(
        "SELECT id::text, login_identifier_hash, password_hash,"
        " auth_provider, is_active FROM public.users"
        " WHERE login_identifier_hash = %s",
        (_hash(email),),
    )
    if not user:
        return {"found": False}
    user_id, login_hash, password_hash, auth_provider, is_active = user[0]
    memberships = sql(
        "SELECT id::text, tenant_id::text, membership_status"
        " FROM public.tenant_memberships WHERE user_id = %s",
        (user_id,),
    )
    roles = []
    for membership in memberships:
        roles.extend(
            sql(
                "SELECT membership_id::text, tenant_id::text, role_code"
                " FROM public.tenant_membership_roles"
                " WHERE membership_id = %s AND tenant_id = %s",
                (membership[0], membership[1]),
            )
        )
    return {
        "found": True,
        "user_id": user_id,
        "login_hash_matches": login_hash == _hash(email),
        "password_hash_bcrypt": str(password_hash or "").startswith("$2"),
        "password_hash_differs_from_clear": bool(password_hash)
        and password_hash != email,
        "auth_provider": auth_provider,
        "is_active": bool(is_active),
        "memberships": [
            {
                "id": row[0],
                "tenant_id": row[1],
                "membership_status": row[2],
            }
            for row in memberships
        ],
        "roles": [
            {"membership_id": row[0], "tenant_id": row[1], "role_code": row[2]}
            for row in roles
        ],
    }


def _tenant_account_evidence(tenant_id: str) -> dict:
    tenant = sql(
        "SELECT name, notification_email, api_key_hash,"
        " shopify_webhook_secret_ciphertext, shopify_webhook_secret_key_id,"
        " stripe_webhook_secret_ciphertext, stripe_webhook_secret_key_id,"
        " paypal_webhook_secret_ciphertext, paypal_webhook_secret_key_id,"
        " woocommerce_webhook_secret_ciphertext,"
        " woocommerce_webhook_secret_key_id"
        " FROM public.tenants WHERE id = %s",
        (tenant_id,),
    )
    if not tenant:
        return {"found": False}
    row = tenant[0]
    api_hash = str(row[2] or "")
    provider_secret_columns = row[3:]
    provider_connections = int(
        sql(
            "SELECT count(*) FROM public.platform_connections"
            " WHERE tenant_id = %s",
            (tenant_id,),
        )[0][0]
    )
    provider_credentials = int(
        sql(
            "SELECT count(*) FROM public.platform_credentials"
            " WHERE tenant_id = %s",
            (tenant_id,),
        )[0][0]
    )
    financial_counts = {}
    for table in (
        "attribution_events",
        "webhook_ingress_identities",
        "b23_match_verdicts",
        "b23_revenue_events",
        "b26_p2_source_money_attestation",
        "attribution_allocations",
        "revenue_ledger",
        "agent_clients",
        "agent_service_credentials",
    ):
        financial_counts[table] = int(
            sql(
                f"SELECT count(*) FROM public.{table} WHERE tenant_id = %s",
                (tenant_id,),
            )[0][0]
        )
    return {
        "found": True,
        "name": row[0],
        "notification_email": row[1],
        "notification_email_is_unavailable_sentinel": (
            row[1] == "unavailable@skeldir.invalid"
        ),
        "api_key_hash_sha256_hex": bool(
            len(api_hash) == 64
            and all(ch in "0123456789abcdef" for ch in api_hash)
        ),
        "provider_secret_columns_all_null": all(
            value is None for value in provider_secret_columns
        ),
        "provider_connections": provider_connections,
        "provider_credentials": provider_credentials,
        "financial_and_source_counts": financial_counts,
    }


def _role_posture() -> dict:
    names = (
        "app_user",
        "app_worker",
        "app_ingress",
        "app_trust_issuer",
        "app_trust_signer",
        "app_relay",
        "app_beat",
        "app_celery_transport",
        "app_dispatch_publisher",
        "app_b28_requester",
        "app_b28_solver",
        "app_ro",
        "app_rw",
    )
    rows = sql(
        "SELECT rolname, rolcanlogin, rolbypassrls, rolsuper"
        " FROM pg_roles WHERE rolname = ANY(%s) ORDER BY rolname",
        (list(names),),
    )
    return {
        str(row[0]): {
            "rolcanlogin": bool(row[1]),
            "rolbypassrls": bool(row[2]),
            "rolsuper": bool(row[3]),
        }
        for row in rows
    }


def _direct_insert_privilege() -> bool:
    return bool(
        sql(
            "SELECT has_table_privilege('app_user',"
            " 'public.users', 'INSERT')"
        )[0][0]
    )


def _provisioner_sensitive_privileges() -> dict:
    tables = (
        "attribution_events",
        "webhook_ingress_identities",
        "b23_match_verdicts",
        "b23_revenue_events",
        "b26_p2_source_money_attestation",
        "trust_envelope_issuance_log",
        "b26_p2_auth_root_evidence",
        "agent_clients",
        "platform_credentials",
    )
    result = {}
    for table in tables:
        row = sql(
            "SELECT has_table_privilege('app_account_provisioner', %s,"
            " 'SELECT'), has_table_privilege('app_account_provisioner', %s,"
            " 'INSERT'), has_table_privilege('app_account_provisioner', %s,"
            " 'UPDATE'), has_table_privilege('app_account_provisioner', %s,"
            " 'DELETE')",
            (
                f"public.{table}",
                f"public.{table}",
                f"public.{table}",
                f"public.{table}",
            ),
        )[0]
        result[table] = {
            "select": bool(row[0]),
            "insert": bool(row[1]),
            "update": bool(row[2]),
            "delete": bool(row[3]),
        }
    execute_rows = sql(
        "SELECT p.oid::regprocedure::text"
        " FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
        " CROSS JOIN LATERAL aclexplode(COALESCE("
        "   p.proacl, acldefault('f', p.proowner))) AS acl"
        " JOIN pg_roles r ON r.oid = acl.grantee"
        " WHERE n.nspname = 'public'"
        " AND r.rolname = 'app_account_provisioner'"
        " AND acl.privilege_type = 'EXECUTE'"
        " AND (p.proname ILIKE '%%attest%%' OR p.proname ILIKE '%%sign%%'"
        "      OR p.proname ILIKE '%%trust%%' OR p.proname ILIKE '%%ingress%%'"
        "      OR p.proname ILIKE '%%source%%' OR p.proname ILIKE '%%money%%')"
        " ORDER BY 1"
    )
    result["sensitive_execute"] = [str(row[0]) for row in execute_rows]
    return result


def _resources_present() -> dict:
    containers = docker(
        "ps", "-a", "--filter", f"name={PREFIX}", "--format", "{{.Names}}"
    ).stdout.strip()
    volumes = docker(
        "volume", "ls", "--filter", f"name={PREFIX}", "--format", "{{.Name}}"
    ).stdout.strip()
    networks = docker(
        "network", "ls", "--filter", f"name={PREFIX}", "--format", "{{.Name}}"
    ).stdout.strip()
    return {
        "containers": [row for row in containers.splitlines() if row],
        "volumes": [row for row in volumes.splitlines() if row],
        "networks": [row for row in networks.splitlines() if row],
    }


def main() -> int:
    checks: dict[str, bool] = {}
    observations: dict = {
        "started_at_utc": _now(),
        "lane": _LANE,
        "fixture_disclosure": {
            "source": "existing XXV lane up command",
            "used_for_walk": False,
            "note": (
                "The lane seeds unrelated control tenants and machine"
                " credentials. No fixture identity, password, key or minted"
                " token is used by this walk."
            ),
        },
        "prohibited_shortcuts_used": {
            "seed_tenant": False,
            "mint_jwt": False,
            "account_insert": False,
            "contract_testing_or_testing_bypass": False,
            "identity_injection": False,
        },
    }
    failures: list[str] = []

    def require(name: str, condition: bool, detail=None) -> None:
        checks[name] = bool(condition)
        if detail is not None:
            observations.setdefault("check_details", {})[name] = detail
        if not condition:
            failures.append(name)

    state: dict = {}
    started = False
    exit_code = 1
    try:
        cmd_up(argparse.Namespace())
        started = True
        state = load_state()
        artifact = state.get("artifact") or {}
        observations["artifact"] = artifact
        observations["fixture_disclosure"]["control_tenant_ids"] = [
            (state.get("tenant_a") or {}).get("tenant_id"),
            (state.get("tenant_b") or {}).get("tenant_id"),
        ]
        require(
            "image_matches_committed_tree",
            bool(
                (artifact.get("worktree_status_summary") or {}).get(
                    "image_bytes_match_committed_tree"
                )
            ),
            artifact.get("worktree_status_summary"),
        )
        require(
            "migration_head_is_supported_signup",
            artifact.get("migration_head") == "202611070001",
            artifact.get("migration_head"),
        )

        password_a = "walk-password-a-123456"
        password_b = "walk-password-b-123456"
        email_a = f"walk.a.{uuid.uuid4().hex}@example.com"
        email_b = f"walk.b.{uuid.uuid4().hex}@example.com"
        workspace_a = f"Walk Business A {uuid.uuid4().hex[:8]}"
        workspace_b = f"Walk Business B {uuid.uuid4().hex[:8]}"

        status_a, body_a = _signup(email_a, password_a, workspace_a)
        status_b, body_b = _signup(email_b, password_b, workspace_b)
        require("signup_a_created", status_a == 201, status_a)
        require("signup_b_created", status_b == 201, status_b)
        require(
            "signup_ids_distinct",
            isinstance(body_a, dict)
            and isinstance(body_b, dict)
            and body_a.get("tenant_id") != body_b.get("tenant_id")
            and body_a.get("user_id") != body_b.get("user_id"),
        )
        tenant_a = str((body_a or {}).get("tenant_id")) if isinstance(body_a, dict) else ""
        tenant_b = str((body_b or {}).get("tenant_id")) if isinstance(body_b, dict) else ""
        user_a = str((body_a or {}).get("user_id")) if isinstance(body_a, dict) else ""
        user_b = str((body_b or {}).get("user_id")) if isinstance(body_b, dict) else ""
        observations["created"] = {
            "a": {"user_id": user_a, "tenant_id": tenant_a},
            "b": {"user_id": user_b, "tenant_id": tenant_b},
        }

        login_a_status, login_a = _login(email_a, password_a)
        login_b_status, login_b = _login(email_b, password_b)
        require("login_a_without_selector", login_a_status == 200, login_a_status)
        require("login_b_without_selector", login_b_status == 200, login_b_status)
        require(
            "login_a_selected_own_tenant",
            isinstance(login_a, dict)
            and str(login_a.get("tenant_id")) == tenant_a
            and str((login_a.get("user") or {}).get("id")) == user_a,
        )
        require(
            "login_b_selected_own_tenant",
            isinstance(login_b, dict)
            and str(login_b.get("tenant_id")) == tenant_b
            and str((login_b.get("user") or {}).get("id")) == user_b,
        )
        token_a = str((login_a or {}).get("access_token") or "") if isinstance(login_a, dict) else ""
        token_b = str((login_b or {}).get("access_token") or "") if isinstance(login_b, dict) else ""
        require("login_a_tokens_present", bool(token_a and (login_a or {}).get("refresh_token")))
        require("login_b_tokens_present", bool(token_b and (login_b or {}).get("refresh_token")))
        verify_a_status, verify_a = _verify(token_a)
        verify_b_status, verify_b = _verify(token_b)
        require("verify_a", verify_a_status == 200, verify_a_status)
        require("verify_b", verify_b_status == 200, verify_b_status)
        require(
            "verify_a_identity",
            isinstance(verify_a, dict)
            and verify_a.get("valid") is True
            and str(verify_a.get("user_id")) == user_a,
        )
        require(
            "verify_b_identity",
            isinstance(verify_b, dict)
            and verify_b.get("valid") is True
            and str(verify_b.get("user_id")) == user_b,
        )
        observations["login"] = {
            "a": {
                "status": login_a_status,
                "selected_tenant_id": (login_a or {}).get("tenant_id") if isinstance(login_a, dict) else None,
                "access_token_present": bool(token_a),
                "refresh_token_present": bool(isinstance(login_a, dict) and login_a.get("refresh_token")),
                "verify_status": verify_a_status,
            },
            "b": {
                "status": login_b_status,
                "selected_tenant_id": (login_b or {}).get("tenant_id") if isinstance(login_b, dict) else None,
                "access_token_present": bool(token_b),
                "refresh_token_present": bool(isinstance(login_b, dict) and login_b.get("refresh_token")),
                "verify_status": verify_b_status,
            },
        }

        wrong_status, wrong_body = _login(email_a, "wrong-password-123456")
        require("wrong_password_refused", wrong_status == 401, wrong_status)
        require(
            "wrong_password_no_token",
            not isinstance(wrong_body, dict)
            or not (
                wrong_body.get("access_token")
                or wrong_body.get("refresh_token")
            ),
        )
        cross_status, cross_body = _login(email_a, password_a, tenant_id=tenant_b)
        require("cross_account_tenant_refused", cross_status == 401, cross_status)
        require(
            "cross_account_tenant_no_token",
            not isinstance(cross_body, dict)
            or not (
                cross_body.get("access_token")
                or cross_body.get("refresh_token")
            ),
        )
        explicit_status, explicit_body = _login(
            email_a, password_a, tenant_id=tenant_a
        )
        require(
            "explicit_own_tenant_succeeds",
            explicit_status == 200
            and isinstance(explicit_body, dict)
            and str(explicit_body.get("tenant_id")) == tenant_a,
            explicit_status,
        )
        observations["selector_checks"] = {
            "wrong_password_status": wrong_status,
            "wrong_password_token_present": bool(
                isinstance(wrong_body, dict)
                and (wrong_body.get("access_token") or wrong_body.get("refresh_token"))
            ),
            "cross_account_status": cross_status,
            "cross_account_token_present": bool(
                isinstance(cross_body, dict)
                and (cross_body.get("access_token") or cross_body.get("refresh_token"))
            ),
            "explicit_own_tenant_status": explicit_status,
        }

        duplicate_email = f"duplicate.{uuid.uuid4().hex}@example.com"
        duplicate_first_workspace = f"Duplicate First {uuid.uuid4().hex[:8]}"
        duplicate_second_workspace = f"Duplicate Second {uuid.uuid4().hex[:8]}"
        dup1_status, _ = _signup(
            duplicate_email, "duplicate-password-123", duplicate_first_workspace
        )
        dup2_status, _ = _signup(
            duplicate_email.upper(), "duplicate-password-123", duplicate_second_workspace
        )
        require("duplicate_first_created", dup1_status == 201, dup1_status)
        require("duplicate_normalized_refused", dup2_status == 409, dup2_status)
        require(
            "duplicate_created_one_identity",
            _user_count(duplicate_email) == 1,
            _user_count(duplicate_email),
        )
        require(
            "duplicate_created_no_partial_tenant",
            _tenant_count(duplicate_second_workspace) == 0,
            _tenant_count(duplicate_second_workspace),
        )

        race_email_base = f"race.{uuid.uuid4().hex}@example.com"
        race_workspace_a = f"Race First {uuid.uuid4().hex[:8]}"
        race_workspace_b = f"Race Second {uuid.uuid4().hex[:8]}"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            race_futures = [
                pool.submit(
                    _signup,
                    race_email_base,
                    "race-password-123456",
                    race_workspace_a,
                ),
                pool.submit(
                    _signup,
                    race_email_base.upper(),
                    "race-password-123456",
                    race_workspace_b,
                ),
            ]
            race_results = [future.result() for future in race_futures]
        race_statuses = sorted(status for status, _ in race_results)
        require(
            "concurrent_duplicate_exactly_one_success",
            race_statuses == [201, 409],
            race_statuses,
        )
        require(
            "concurrent_duplicate_one_identity",
            _user_count(race_email_base) == 1,
            _user_count(race_email_base),
        )
        require(
            "concurrent_duplicate_one_workspace",
            _tenant_count(race_workspace_a) + _tenant_count(race_workspace_b) == 1,
            [
                _tenant_count(race_workspace_a),
                _tenant_count(race_workspace_b),
            ],
        )

        invalid_totals_before = _account_totals()
        invalid_cases = [
            (f"invalid.workspace.{uuid.uuid4().hex}@example.com", "invalid-password-123", "   ", None),
            (f"invalid.short.{uuid.uuid4().hex}@example.com", "short", "Invalid Short", None),
            (
                f"invalid.extra.tenant.{uuid.uuid4().hex}@example.com",
                "invalid-password-123",
                "Invalid Extra Tenant",
                {"tenant_id": str(uuid.uuid4())},
            ),
            (
                f"invalid.extra.role.{uuid.uuid4().hex}@example.com",
                "invalid-password-123",
                "Invalid Extra Role",
                {"role": "admin"},
            ),
        ]
        invalid_statuses = []
        for email, password, workspace, extra in invalid_cases:
            status, _ = _signup(email, password, workspace, extra=extra)
            invalid_statuses.append(status)
        require(
            "invalid_inputs_governed_422",
            invalid_statuses == [422, 422, 422, 422],
            invalid_statuses,
        )
        require(
            "invalid_inputs_create_no_accounts",
            all(_user_count(email) == 0 for email, *_ in invalid_cases),
        )
        require(
            "invalid_inputs_no_partial_account_tables",
            _account_totals() == invalid_totals_before,
            {
                "before": invalid_totals_before,
                "after": _account_totals(),
            },
        )

        account_a = _account_rows(email_a)
        account_b = _account_rows(email_b)
        tenant_evidence_a = _tenant_account_evidence(tenant_a)
        tenant_evidence_b = _tenant_account_evidence(tenant_b)
        observations["account_evidence"] = {
            "a": {"account": account_a, "tenant": tenant_evidence_a},
            "b": {"account": account_b, "tenant": tenant_evidence_b},
        }
        for label, account, tenant_evidence, workspace in (
            ("a", account_a, tenant_evidence_a, workspace_a),
            ("b", account_b, tenant_evidence_b, workspace_b),
        ):
            require(
                f"account_{label}_login_hash_matches",
                account.get("login_hash_matches") is True,
            )
            require(
                f"account_{label}_password_is_bcrypt_hash",
                account.get("password_hash_bcrypt") is True,
            )
            require(
                f"account_{label}_password_provider_active",
                account.get("auth_provider") == "password"
                and account.get("is_active") is True,
            )
            require(
                f"account_{label}_one_active_membership",
                len(account.get("memberships") or []) == 1
                and (account.get("memberships") or [{}])[0].get(
                    "membership_status"
                )
                == "active"
                and (account.get("memberships") or [{}])[0].get("tenant_id")
                == (tenant_a if label == "a" else tenant_b),
            )
            memberships = account.get("memberships") or [{}]
            roles = account.get("roles") or []
            require(
                f"account_{label}_admin_role_only_new_tenant",
                len(roles) == 1
                and roles[0].get("role_code") == "admin"
                and roles[0].get("tenant_id") == memberships[0].get("tenant_id")
                and roles[0].get("membership_id") == memberships[0].get("id"),
            )
            require(
                f"account_{label}_workspace_name",
                tenant_evidence.get("name") == workspace,
            )
            require(
                f"account_{label}_notification_sentinel",
                tenant_evidence.get("notification_email_is_unavailable_sentinel")
                is True,
            )
            require(
                f"account_{label}_api_key_hash_discarded_shape",
                tenant_evidence.get("api_key_hash_sha256_hex") is True,
            )
            require(
                f"account_{label}_no_provider_secret",
                tenant_evidence.get("provider_secret_columns_all_null") is True,
            )
            require(
                f"account_{label}_no_provider_connection",
                tenant_evidence.get("provider_connections") == 0
                and tenant_evidence.get("provider_credentials") == 0,
            )
            require(
                f"account_{label}_no_financial_or_source_record",
                all(
                    count == 0
                    for count in (
                        tenant_evidence.get("financial_and_source_counts") or {}
                    ).values()
                ),
                tenant_evidence.get("financial_and_source_counts"),
            )

        grant_email = f"grant.{uuid.uuid4().hex}@example.com"
        grant_workspace = f"Grant Restore {uuid.uuid4().hex[:8]}"
        before_revoke_totals = _account_totals()
        privileged_before = bool(
            sql(
                "SELECT has_function_privilege('app_user',"
                " 'auth.register_business_account(text,text,text)',"
                " 'EXECUTE')"
            )[0][0]
        )
        sql(
            "REVOKE EXECUTE ON FUNCTION"
            " auth.register_business_account(text,text,text) FROM app_user"
        )
        try:
            revoked_status, _ = _signup(
                grant_email, "grant-password-123456", grant_workspace
            )
            revoked_privilege = bool(
                sql(
                    "SELECT has_function_privilege('app_user',"
                    " 'auth.register_business_account(text,text,text)',"
                    " 'EXECUTE')"
                )[0][0]
            )
            after_revoke_totals = _account_totals()
            require(
                "signup_refused_without_execute",
                revoked_status != 201,
                revoked_status,
            )
            require(
                "signup_without_execute_created_nothing",
                _user_count(grant_email) == 0
                and after_revoke_totals == before_revoke_totals,
                {
                    "status": revoked_status,
                    "privilege": revoked_privilege,
                    "before": before_revoke_totals,
                    "after": after_revoke_totals,
                },
            )
        finally:
            sql(
                "GRANT EXECUTE ON FUNCTION"
                " auth.register_business_account(text,text,text) TO app_user"
            )
        restored_privilege = bool(
            sql(
                "SELECT has_function_privilege('app_user',"
                " 'auth.register_business_account(text,text,text)',"
                " 'EXECUTE')"
            )[0][0]
        )
        restored_status, restored_body = _signup(
            grant_email, "grant-password-123456", grant_workspace
        )
        restored_login_status, restored_login = _login(
            grant_email, "grant-password-123456"
        )
        require("execute_grant_was_present", privileged_before, privileged_before)
        require("execute_grant_restored_exactly", restored_privilege is True)
        require(
            "same_uncreated_signup_succeeds_after_restore",
            restored_status == 201,
            restored_status,
        )
        require(
            "restored_signup_logs_in",
            restored_login_status == 200
            and isinstance(restored_login, dict)
            and str(restored_login.get("tenant_id"))
            == str((restored_body or {}).get("tenant_id")),
            restored_login_status,
        )

        provisioner = sql(
            "SELECT rolcanlogin, rolbypassrls FROM pg_roles"
            " WHERE rolname = 'app_account_provisioner'"
        )
        require(
            "provisioner_is_nologin_bypassrls",
            bool(provisioner)
            and provisioner[0][0] is False
            and provisioner[0][1] is True,
            provisioner,
        )
        runtime_posture = _role_posture()
        inherited = [
            name
            for name in runtime_posture
            if bool(
                sql(
                    "SELECT pg_has_role(%s, 'app_account_provisioner',"
                    " 'MEMBER')",
                    (name,),
                )[0][0]
            )
        ]
        require("no_runtime_role_inherits_provisioner", inherited == [], inherited)
        require(
            "app_user_cannot_directly_insert_identity",
            _direct_insert_privilege() is False,
        )
        sensitive = _provisioner_sensitive_privileges()
        require(
            "provisioner_has_no_financial_provider_signing_table_authority",
            all(
                not any(value.values())
                for key, value in sensitive.items()
                if isinstance(value, dict)
            ),
            sensitive,
        )
        require(
            "provisioner_has_no_sensitive_function_authority",
            sensitive.get("sensitive_execute") == [],
            sensitive.get("sensitive_execute"),
        )
        observations["role_posture"] = {
            "runtime_roles": runtime_posture,
            "provisioner_can_login": bool(provisioner[0][0]) if provisioner else None,
            "provisioner_has_bypassrls": bool(provisioner[0][1]) if provisioner else None,
            "runtime_roles_inheriting_provisioner": inherited,
            "app_user_direct_users_insert": _direct_insert_privilege(),
            "provisioner_sensitive_privileges": sensitive,
        }

        exit_code = 0 if not failures else 1
    except Exception as exc:  # noqa: BLE001
        failures.append(f"walk_exception:{type(exc).__name__}:{exc}")
        exit_code = 1
    finally:
        teardown: dict = {}
        try:
            cmd_down(argparse.Namespace())
            for image in (BOOTSTRAP_IMAGE, FINAL_IMAGE):
                docker("image", "rm", "-f", image)
            shutil.rmtree(LANE_ROOT, ignore_errors=True)
            resources = _resources_present()
            teardown = {
                "command": "b26_p2_xxv_lane.py down + prefix image removal",
                "resources_after": resources,
                "resources_absent": not any(resources.values()),
            }
            if not teardown["resources_absent"]:
                failures.append("deployment_resources_retained")
                exit_code = 1
        except Exception as exc:  # noqa: BLE001
            teardown = {
                "error": f"{type(exc).__name__}:{exc}",
                "resources_absent": False,
            }
            failures.append("teardown_failed")
            exit_code = 1
        observations["teardown"] = teardown
        observations["finished_at_utc"] = _now()
        observations["checks"] = checks
        observations["failures"] = failures
        observations["passed"] = bool(not failures and started and exit_code == 0)
        RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULT_PATH.write_text(
            json.dumps(observations, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "result": str(RESULT_PATH),
                    "passed": observations["passed"],
                    "failure_count": len(failures),
                    "failures": failures,
                    "checks": checks,
                    "teardown": teardown,
                },
                indent=2,
                sort_keys=True,
            )
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
