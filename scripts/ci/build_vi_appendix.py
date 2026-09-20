"""Rebuild the Corrective VI canonical appendix from the migration (safe).

Only the upgrade() half is read. Function bodies are located by their
CREATE line and terminated at their own $$; terminator line -- never by
cross-block regex. Writes the appendix and splices it into
canonical_schema.sql ahead of the pg_dump trailer in binary mode (LF).
"""

import re
from pathlib import Path

MIG = Path(
    "alembic/versions/007_skeldir_foundation/"
    "202609200001_b26_p2_corrective_vi_sovereign_root.py"
)
CANON = Path("db/schema/canonical_schema.sql")

mig = MIG.read_text(encoding="utf-8")
upgrade_half = mig.split("\ndef downgrade")[0]

FUNCTIONS = [
    "b26_p2_canonical_day_start",
    "b26_p2_canonical_day_end",
    "b26_p2_enforce_dispatch_sovereign_window",
    "b26_p2_enforce_ingress_sovereign_custody",
    "b26_p2_enforce_dispatch_immutability",
    "b26_p2_enforce_outbox_issuance",
    "b26_p2_enforce_outbox_transitions",
    "b26_p2_resolve_dispatch_authority",
    "b26_p2_record_conduction_receipt",
    "b26_p2_mark_conducted",
    "b26_p2_stale_unconducted",
    "b26_p2_operational_disposition",
]

bodies: dict[str, str] = {}
for name in FUNCTIONS:
    marker = f"        CREATE OR REPLACE FUNCTION public.{name}("
    start = upgrade_half.find(marker)
    assert start != -1, name
    # Terminator: a line that is exactly 8 spaces + END $$; or $$; .
    tail = upgrade_half[start:]
    m = re.search(r"\n        (END )?\$\$;", tail)
    assert m, name
    end = m.end()
    body = tail[:end]
    assert body.count("CREATE OR REPLACE FUNCTION public.") == 1, name
    # NO dedent: the migration lane stores the SQL text verbatim,
    # including its Python-block indentation. The bootstrap lane must
    # carry character-identical bodies (the equivalence proof compares
    # pg_get_functiondef text), so the canonical copy keeps the exact
    # migration bytes.
    assert body.startswith("        CREATE OR REPLACE FUNCTION public." + name)
    bodies[name] = body
    print("extracted", name, len(body))

HAND_TOP = """--
-- B2.6-P2 Corrective VI: sovereign root appendix (mirrors migration 202609200001 final state verbatim).
--

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'b23_match_task_dispatches'
          AND column_name = 'first_published_at'
    ) THEN
        ALTER TABLE public.b23_match_task_dispatches
            ADD COLUMN first_published_at timestamp with time zone NULL;
    END IF;
END $$;

"""

HAND_COMMENT = """COMMENT ON FUNCTION public.b26_p2_canonical_day_start(timestamptz) IS
    'B2.6-P2 Corrective VI sovereign UTC-day quantization: SQL parity
    copy of app.core.day_window.quantize_utc_day (parity-oracle tested).';
COMMENT ON FUNCTION public.b26_p2_canonical_day_end(timestamptz) IS
    'B2.6-P2 Corrective VI sovereign UTC-day quantization end bound.';

ALTER TABLE public.b26_p2_execution_quarantine
    DROP CONSTRAINT IF EXISTS ck_b26_p2_quarantine_source;
ALTER TABLE public.b26_p2_execution_quarantine
    ADD CONSTRAINT ck_b26_p2_quarantine_source
    CHECK (source_relation IN (
        'b26_p2_execution_outbox',
        'b26_p2_task_authority_directory',
        'b23_match_task_dispatches',
        'b26_p2_conduction_receipts'
    ));

"""

HAND_SOVEREIGN_TRIGGER = """DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_b26_p2_dispatch_sovereign_window'
    ) THEN
        CREATE TRIGGER trg_b26_p2_dispatch_sovereign_window
        BEFORE INSERT OR UPDATE OF
            window_start, window_end,
            webhook_ingress_identity_id, tenant_id, provider
        ON public.b23_match_task_dispatches
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_enforce_dispatch_sovereign_window();
    END IF;
END $$;

"""

HAND_CUSTODY_TRIGGER = """DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_b26_p2_ingress_sovereign_custody'
    ) THEN
        CREATE TRIGGER trg_b26_p2_ingress_sovereign_custody
        BEFORE UPDATE OF event_timestamp, tenant_id, provider
            OR DELETE
        ON public.webhook_ingress_identities
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_enforce_ingress_sovereign_custody();
    END IF;
END $$;

"""

HAND_OUTBOX_ISSUANCE_TRIGGER = """DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_b26_p2_outbox_issuance'
    ) THEN
        CREATE TRIGGER trg_b26_p2_outbox_issuance
        BEFORE INSERT ON public.b26_p2_execution_outbox
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_enforce_outbox_issuance();
    END IF;
END $$;

"""

HAND_IMMUTABILITY_TRIGGER = """DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_b26_p2_dispatch_immutability'
    ) THEN
        DROP TRIGGER trg_b26_p2_dispatch_immutability
            ON public.b23_match_task_dispatches;
    END IF;
    CREATE TRIGGER trg_b26_p2_dispatch_immutability
    BEFORE INSERT OR UPDATE ON public.b23_match_task_dispatches
    FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_dispatch_immutability();
END $$;

"""

parts = [
    HAND_TOP,
    bodies["b26_p2_canonical_day_start"] + ";\n\n",
    bodies["b26_p2_canonical_day_end"] + ";\n\n",
    HAND_COMMENT,
    bodies["b26_p2_enforce_dispatch_sovereign_window"] + ";\n\n",
    HAND_SOVEREIGN_TRIGGER,
    bodies["b26_p2_enforce_ingress_sovereign_custody"] + ";\n\n",
    HAND_CUSTODY_TRIGGER,
    bodies["b26_p2_enforce_outbox_issuance"] + ";\n\n",
    bodies["b26_p2_enforce_outbox_transitions"] + ";\n\n",
    HAND_OUTBOX_ISSUANCE_TRIGGER,
    bodies["b26_p2_enforce_dispatch_immutability"] + ";\n\n",
    HAND_IMMUTABILITY_TRIGGER,
    bodies["b26_p2_resolve_dispatch_authority"] + ";\n\n",
    bodies["b26_p2_record_conduction_receipt"] + ";\n\n",
    bodies["b26_p2_mark_conducted"] + ";\n\n",
    bodies["b26_p2_stale_unconducted"] + ";\n\n",
    bodies["b26_p2_operational_disposition"] + ";\n\n",
]

# Bodies end at the $$; terminator; the statement needs the final semicolon
# only when the terminator line lacks it. Our extraction ends WITH $$;
# (e.g. "END $$;") which already terminates the statement, so appending
# ";" would emit "$$;;" -- instead ensure exactly one terminator.
fixed = []
for part in parts:
    fixed.append(part)
appendix = "".join(fixed)
# Remove accidental double semicolons after $$; terminators.
appendix = appendix.replace("$$;;", "$$;")

canon = CANON.read_bytes().replace(b"\r\n", b"\n")
trailer = b"-- PostgreSQL database dump complete"
assert canon.count(trailer) == 1
out = canon.replace(trailer, appendix.encode("utf-8") + b"\n" + trailer)
assert b"\r" not in out
CANON.write_bytes(out)
print("appendix bytes:", len(appendix), "total:", len(out))
