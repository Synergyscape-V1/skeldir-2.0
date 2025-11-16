"""Add PII audit table and scanning function

Revision ID: 202511161210
Revises: 202511161200
Create Date: 2025-11-16 12:10:00

Migration Description:
Implements Layer 3 (Operations Audit & Monitoring) of the PII Defense-in-Depth strategy
as documented in ADR-003-PII-Defense-Strategy.md.

Creates audit table and scanning function to detect residual PII contamination even if
Layer 1 (B0.4 app) or Layer 2 (database guardrail) fail.

Objects Created:
1. pii_audit_findings - Table storing PII detection findings
2. fn_scan_pii_contamination() - Function scanning all three JSONB surfaces for PII keys
3. Index on (table_name, detected_at DESC) for query performance
4. GRANTs for app_rw and app_ro roles

Purpose:
- Detects Layer 1/Layer 2 failures
- Provides operational visibility into PII risk
- Enables compliance auditing and incident response
- Continuous validation of "no persistent PII" mandate

Operational Schedule (to be configured):
- Non-prod: Daily batch scan
- Production: Hourly or daily batch scan (based on volume)
- Alerting: Non-zero findings count → incident response

References:
- ADR-003: db/docs/adr/ADR-003-PII-Defense-Strategy.md (Layer 3 section)
- Implementation: B0.3-P_PII_DEFENSE.md (Phase 3)
- Layer 2: Migration 202511161200_add_pii_guardrail_triggers.py
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511161210'
down_revision: Union[str, None] = '202511161200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Apply PII audit table and scanning function.
    
    Creates:
    1. pii_audit_findings table for storing PII detection findings
    2. fn_scan_pii_contamination() function for batch scanning
    3. Performance indexes
    4. GRANTs for application roles
    """
    
    # ========================================================================
    # Step 1: Create PII Audit Findings Table
    # ========================================================================
    
    op.execute("""
        CREATE TABLE pii_audit_findings (
            id BIGSERIAL PRIMARY KEY,
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            record_id UUID NOT NULL,
            detected_key TEXT NOT NULL,
            sample_snippet TEXT,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    
    op.execute("""
        COMMENT ON TABLE pii_audit_findings IS
            'PII audit findings repository (Layer 3 operations audit). Purpose: Store PII contamination detections from periodic scans. Data class: Non-PII (contains record IDs and key names only, not actual PII values). Ownership: Operations/Security team. Use: Detect Layer 1/Layer 2 failures, compliance auditing, incident response. Schedule: Daily (non-prod), Hourly/Daily (prod). Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 3 (Operations)".'
    """)
    
    op.execute("""
        COMMENT ON COLUMN pii_audit_findings.table_name IS
            'Source table where PII was detected (attribution_events, dead_events, or revenue_ledger). Purpose: Identify contamination source for remediation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN pii_audit_findings.column_name IS
            'Source column where PII was detected (raw_payload or metadata). Purpose: Identify contamination location.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN pii_audit_findings.record_id IS
            'UUID of the contaminated record. Purpose: Enable record-level remediation and investigation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN pii_audit_findings.detected_key IS
            'PII key that was detected (e.g., email, phone, ssn). Purpose: Identify PII category for compliance reporting.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN pii_audit_findings.sample_snippet IS
            'Optional snippet of contaminated payload (redacted). Purpose: Aid investigation without exposing full PII. May be NULL.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN pii_audit_findings.detected_at IS
            'Timestamp when PII was detected by audit scan. Purpose: Track detection timing for SLA and incident response.'
    """)
    
    # ========================================================================
    # Step 2: Create Performance Indexes
    # ========================================================================
    
    op.execute("""
        CREATE INDEX idx_pii_audit_findings_table_detected_at 
        ON pii_audit_findings (table_name, detected_at DESC)
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_pii_audit_findings_table_detected_at IS
            'Performance index for table-scoped queries with time ordering. Purpose: Fast queries like "show recent findings for attribution_events". Query pattern: WHERE table_name = X ORDER BY detected_at DESC.'
    """)
    
    op.execute("""
        CREATE INDEX idx_pii_audit_findings_detected_key 
        ON pii_audit_findings (detected_key)
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_pii_audit_findings_detected_key IS
            'Performance index for PII category reporting. Purpose: Fast aggregation queries like "count findings by PII type". Query pattern: WHERE detected_key = X OR GROUP BY detected_key.'
    """)
    
    # ========================================================================
    # Step 3: Create PII Scanning Function
    # ========================================================================
    
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_scan_pii_contamination()
        RETURNS INTEGER AS $$
        DECLARE
            finding_count INTEGER := 0;
            rec RECORD;
            detected_key_var TEXT;
        BEGIN
            -- Scan attribution_events.raw_payload
            FOR rec IN 
                SELECT id, raw_payload 
                FROM attribution_events 
                WHERE fn_detect_pii_keys(raw_payload)
            LOOP
                -- Find first PII key
                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(rec.raw_payload) key
                WHERE key IN (
                    'email', 'email_address', 
                    'phone', 'phone_number', 
                    'ssn', 'social_security_number', 
                    'ip_address', 'ip', 
                    'first_name', 'last_name', 'full_name', 
                    'address', 'street_address'
                )
                LIMIT 1;
                
                INSERT INTO pii_audit_findings (
                    table_name, 
                    column_name, 
                    record_id, 
                    detected_key,
                    sample_snippet
                )
                VALUES (
                    'attribution_events', 
                    'raw_payload', 
                    rec.id, 
                    detected_key_var,
                    'Redacted for security'  -- Do not log actual PII values
                );
                
                finding_count := finding_count + 1;
            END LOOP;
            
            -- Scan dead_events.raw_payload
            FOR rec IN 
                SELECT id, raw_payload 
                FROM dead_events 
                WHERE fn_detect_pii_keys(raw_payload)
            LOOP
                -- Find first PII key
                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(rec.raw_payload) key
                WHERE key IN (
                    'email', 'email_address', 
                    'phone', 'phone_number', 
                    'ssn', 'social_security_number', 
                    'ip_address', 'ip', 
                    'first_name', 'last_name', 'full_name', 
                    'address', 'street_address'
                )
                LIMIT 1;
                
                INSERT INTO pii_audit_findings (
                    table_name, 
                    column_name, 
                    record_id, 
                    detected_key,
                    sample_snippet
                )
                VALUES (
                    'dead_events', 
                    'raw_payload', 
                    rec.id, 
                    detected_key_var,
                    'Redacted for security'
                );
                
                finding_count := finding_count + 1;
            END LOOP;
            
            -- Scan revenue_ledger.metadata (only non-NULL)
            FOR rec IN 
                SELECT id, metadata 
                FROM revenue_ledger 
                WHERE metadata IS NOT NULL AND fn_detect_pii_keys(metadata)
            LOOP
                -- Find first PII key
                SELECT key INTO detected_key_var
                FROM jsonb_object_keys(rec.metadata) key
                WHERE key IN (
                    'email', 'email_address', 
                    'phone', 'phone_number', 
                    'ssn', 'social_security_number', 
                    'ip_address', 'ip', 
                    'first_name', 'last_name', 'full_name', 
                    'address', 'street_address'
                )
                LIMIT 1;
                
                INSERT INTO pii_audit_findings (
                    table_name, 
                    column_name, 
                    record_id, 
                    detected_key,
                    sample_snippet
                )
                VALUES (
                    'revenue_ledger', 
                    'metadata', 
                    rec.id, 
                    detected_key_var,
                    'Redacted for security'
                );
                
                finding_count := finding_count + 1;
            END LOOP;
            
            RETURN finding_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        COMMENT ON FUNCTION fn_scan_pii_contamination() IS
            'PII contamination scanning function (Layer 3 operations audit). Returns: Count of PII findings detected. Scope: Scans all three JSONB surfaces (attribution_events.raw_payload, dead_events.raw_payload, revenue_ledger.metadata). Behavior: Inserts findings into pii_audit_findings table for each detected PII key. Performance: Batch operation, intended for periodic scheduled execution (not per-transaction). Security: Does not log actual PII values, only record IDs and key names. Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 3 (Operations)".'
    """)
    
    # ========================================================================
    # Step 4: Apply GRANTs
    # ========================================================================
    
    # Grant SELECT to app_rw (for application queries)
    op.execute("GRANT SELECT ON TABLE pii_audit_findings TO app_rw")
    
    # Grant SELECT to app_ro (for reporting and analytics)
    op.execute("GRANT SELECT ON TABLE pii_audit_findings TO app_ro")
    
    # Grant USAGE on sequence to app_rw (needed for potential future direct INSERTs)
    op.execute("GRANT USAGE, SELECT ON SEQUENCE pii_audit_findings_id_seq TO app_rw")
    
    # Revoke PUBLIC access
    op.execute("REVOKE ALL ON TABLE pii_audit_findings FROM PUBLIC")


def downgrade() -> None:
    """
    Rollback PII audit table and scanning function.
    
    Removes:
    1. GRANTs on pii_audit_findings
    2. fn_scan_pii_contamination() function
    3. Indexes on pii_audit_findings
    4. pii_audit_findings table
    
    WARNING: Downgrading removes Layer 3 PII auditing. Historical audit findings
    will be lost. Consider exporting data before downgrade if needed for compliance.
    """
    
    # Revoke GRANTs
    op.execute("REVOKE ALL ON TABLE pii_audit_findings FROM app_rw")
    op.execute("REVOKE ALL ON TABLE pii_audit_findings FROM app_ro")
    op.execute("REVOKE ALL ON SEQUENCE pii_audit_findings_id_seq FROM app_rw")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS fn_scan_pii_contamination()")
    
    # Drop indexes (will be dropped automatically with table, but explicit for clarity)
    op.execute("DROP INDEX IF EXISTS idx_pii_audit_findings_table_detected_at")
    op.execute("DROP INDEX IF EXISTS idx_pii_audit_findings_detected_key")
    
    # Drop table
    op.execute("DROP TABLE IF EXISTS pii_audit_findings CASCADE")

