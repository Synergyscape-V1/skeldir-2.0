# Channel Governance Contract

**Version:** 1.0  
**Status:** Authoritative  
**Ownership:** Attribution Service  
**Related:** B0.3 Channel Governance Remediation, Directive 69

---

## 1. Canonical Channel Domain

### 1.1 Authoritative Channel Taxonomy

All persisted channel values in the Skeldir attribution system **MUST** belong to the canonical set defined in the `channel_taxonomy` table. This is the single source of truth for channel codes across all services, tables, and integrations.

**Database Contract:**
- **Table:** `channel_taxonomy`
- **Primary Key:** `code` (TEXT)
- **Enforcement:** Foreign Key constraints on `attribution_events.channel` and `attribution_allocations.channel_code`

### 1.2 Canonical Channel Codes

The following canonical channel codes are currently defined:

| Code | Family | Paid | Display Name | Semantics |
|------|--------|------|--------------|-----------|
| `unknown` | direct | No | Unknown / Unclassified | **Fallback for unmapped inputs** (see Section 2) |
| `direct` | direct | No | Direct | Direct traffic with no referrer |
| `email` | email | No | Email | Email campaign traffic |
| `facebook_brand` | paid_social | Yes | Facebook Brand | Facebook brand awareness campaigns |
| `facebook_paid` | paid_social | Yes | Facebook Paid | Paid Facebook advertising |
| `google_display_paid` | paid_search | Yes | Google Display Paid | Google Display Network campaigns |
| `google_search_paid` | paid_search | Yes | Google Search Paid | Google Search Ads campaigns |
| `organic` | organic | No | Organic | Organic search and social traffic |
| `referral` | referral | No | Referral | Referral traffic from external sites |
| `tiktok_paid` | paid_social | Yes | TikTok Paid | Paid TikTok advertising |

**Update Process:**
- New canonical codes MUST be added via Alembic migration to `channel_taxonomy`
- New codes MUST be documented in `channel_mapping.yaml`
- Changes require attribution service lead approval

### 1.3 Storage Constraints

**Canonical Channel Columns** (DB-enforced via FK constraints):
- `attribution_events.channel` → MUST contain canonical code from `channel_taxonomy.code`
- `attribution_allocations.channel_code` → MUST contain canonical code from `channel_taxonomy.code`

**Raw Vendor Strings** (Not DB-enforced):
- `attribution_events.raw_payload` → JSON field may contain original vendor indicators (e.g., `utm_source`, `utm_medium`, `utm_campaign`)
- `attribution_events.metadata` → May contain implementation-specific transient values
- **Rule:** Raw vendor labels MUST NOT be stored in canonical `channel` or `channel_code` columns

**Explicit Contract Statement:**

> **No persisted `channel` or `channel_code` value may contain strings outside the `channel_taxonomy.code` set. This contract is enforced at the database boundary via Foreign Key constraints.**

---

## 2. Unmapped Channel Behavior

### 2.1 Canonical Fallback Rule

When the ingestion service (B0.4) encounters channel indicators that cannot be mapped to a canonical code, it **MUST** use the `'unknown'` fallback code.

**Normalization Contract:**

The `normalize_channel()` function (implemented in `backend/app/ingestion/channel_normalization.py`) guarantees:

> **`normalize_channel()` always returns either a valid taxonomy code or `'unknown'`. It NEVER returns `None`, empty strings, or arbitrary non-taxonomy values.**

**Function Signature:**
```python
def normalize_channel(
    utm_source: str | None,
    utm_medium: str | None,
    vendor: str | None
) -> str:
    """
    Map vendor-specific channel indicators to canonical channel codes.
    
    Returns:
        Canonical channel code from channel_taxonomy, or 'unknown' if unmapped.
        GUARANTEE: Never returns None or non-taxonomy strings.
    """
```

### 2.2 Semantics of 'unknown'

**Meaning:**
- `'unknown'` represents traffic or revenue that was observed but could not be classified into a known marketing channel at ingestion time
- It indicates a **data quality gap**, not a business-level marketing channel

**Financial Treatment:**
- Events and allocations with `channel='unknown'` or `channel_code='unknown'` **ARE included** in all financial totals (revenue, conversions, etc.)
- They are **separated** as their own bucket in channel performance analytics and reporting
- Dashboards SHOULD label it clearly as "Unknown / Unclassified" to distinguish from actual "Direct" traffic

**Operational Status:**
- `'unknown'` is **active** and **available for use** in the taxonomy
- It is a **safety net**, not a permanent dumping ground
- High or growing `'unknown'` rates indicate a need for mapping updates (see Section 3)

### 2.3 Deterministic Behavior

The system MUST exhibit deterministic behavior for unmapped channels:

1. **Ingestion (B0.4):**
   - Vendor channel indicators that don't match `channel_mapping.yaml` → `normalize_channel()` returns `'unknown'`
   - Event is inserted with `channel='unknown'`
   - FK constraint on `attribution_events.channel` **allows** this insertion (because `'unknown'` exists in taxonomy)
   - No FK violation, no ingestion failure

2. **Attribution (B2.1):**
   - Attribution engine reads events with `channel='unknown'`
   - Creates allocations with `channel_code='unknown'`
   - FK constraint on `attribution_allocations.channel_code` **allows** this insertion
   - Attribution processing continues without error

3. **Reporting:**
   - `'unknown'` channel appears in all channel performance queries and dashboards
   - Clearly labeled as "Unknown / Unclassified"
   - Included in revenue totals but flagged for investigation

**Critical Property: No Pipeline Failures**

> Unmapped vendor channels MUST NEVER cause FK violations, ingestion failures, or attribution pipeline crashes. The `'unknown'` fallback guarantees graceful degradation with full observability.

---

## 3. Data Quality Strategy

### 3.1 Logging & Observability

All occurrences of `'unknown'` channel assignments **MUST** be logged with sufficient context for investigation and remediation.

**Required Log Fields:**
- `tenant_id` → Which tenant experienced the unmapped channel
- `raw_key` → The full vendor indicator combination (e.g., `"google_ads/SEARCH/cpc"`)
- `utm_source` → Original UTM source parameter (if available)
- `utm_medium` → Original UTM medium parameter (if available)
- `utm_campaign` → Original UTM campaign parameter (if available)
- `vendor` → Vendor/integration identifier (e.g., `"shopify"`, `"google_ads"`)
- `timestamp` → When the unmapped event occurred

**Log Level:** INFO (not WARNING) to avoid alert fatigue, but structured for aggregation

**Implementation:** `log_unmapped_channel()` function in `backend/app/ingestion/channel_normalization.py`

### 3.2 Metrics & Monitoring

The system MUST emit metrics for unmapped channel occurrences to enable proactive monitoring and alerting.

**Required Metrics:**
- `unmapped_channel.count` → Counter of unmapped channel occurrences
  - Tags: `vendor`, `raw_key`, `tenant_id`
  - Increment: Every time `normalize_channel()` returns `'unknown'`
- `unmapped_channel_ratio` → Percentage of events with `channel='unknown'`
  - Per-tenant calculation: `(events with channel='unknown') / (total events)`
  - Global calculation: Aggregate across all tenants

**Monitoring Integration:**
- Metrics SHOULD be exported to Prometheus or equivalent observability platform
- Dashboards SHOULD visualize `unmapped_channel.count` by vendor and tenant
- Alerts SHOULD trigger when `unmapped_channel_ratio` exceeds thresholds (see Section 3.3)

### 3.3 Incident Thresholds

Significant or growing `'unknown'` rates are treated as **data quality incidents** requiring investigation and remediation.

**Operational Thresholds:**

| Threshold | Severity | Action |
|-----------|----------|--------|
| `unmapped_channel_ratio` > 5% per tenant over 7 days | WARNING | Review tenant-specific mapping gaps |
| `unmapped_channel_ratio` > 10% per tenant over 7 days | ERROR | Create internal incident ticket, notify customer success |
| `unmapped_channel.count` > 100 for single vendor/raw_key over 24 hours | WARNING | Add mapping to `channel_mapping.yaml` |
| New vendor appears with no mapping | INFO | Proactive notification to BI/data team |

**Remediation Process:**
1. Review logs/metrics to identify specific unmapped `raw_key` values
2. Determine correct canonical channel code for each unmapped combination
3. Update `channel_mapping.yaml` with new vendor mappings
4. Deploy updated mapping file
5. (Optional) Backfill historical events if needed (manual data repair)

**Key Principle:**

> `'unknown'` is a **temporary state** for new or misconfigured channels. The goal is to drive `unmapped_channel_ratio` toward zero through continuous mapping improvements.

---

## 4. Enforcement Mechanisms

### 4.1 Database-Level Enforcement

**Foreign Key Constraints:**
- `fk_attribution_events_channel` → `attribution_events.channel` references `channel_taxonomy.code`
- `fk_attribution_allocations_channel_code` → `attribution_allocations.channel_code` references `channel_taxonomy.code`

**Behavior:**
- Database rejects any `INSERT` or `UPDATE` that attempts to set `channel` or `channel_code` to a non-taxonomy value
- Includes `'unknown'` as a valid canonical code (post-migration `202511161120`)
- Prevents data corruption at the lowest level (DB boundary)

**Verification:**
- CI validation scripts check for FK presence (see `scripts/validate_channel_fks.py`)
- Data integrity checks run periodically to ensure zero non-taxonomy values (see `scripts/validate_channel_integrity.py`)

### 4.2 Application-Level Enforcement

**Normalization Function:**
- `normalize_channel()` is the **sole entry point** for channel value determination
- All ingestion code paths MUST call `normalize_channel()` before persisting events
- Direct assignment of `channel` values is **prohibited** (violates contract)

**Testing:**
- Golden test suite validates `normalize_channel()` behavior (see `backend/tests/test_channel_normalization.py`)
- CI pipeline executes tests on every commit
- Breaking the normalization contract (e.g., returning non-taxonomy strings) MUST cause CI failure

### 4.3 Continuous Integrity Checks

**Schema Validation:**
- Script: `scripts/validate_channel_fks.py`
- Frequency: On schema changes, in CI
- Purpose: Verify FK constraints exist and have correct definitions

**Data Integrity:**
- Script: `scripts/validate_channel_integrity.py`
- Frequency: Daily in production, on-demand in dev/staging
- Purpose: Detect any non-taxonomy channel values that bypassed FK constraints (should be zero)

**Monitoring:**
- Metrics: `unmapped_channel.count`, `unmapped_channel_ratio`
- Frequency: Real-time metric collection
- Purpose: Track data quality and identify mapping gaps proactively

---

## 5. Change Management

### 5.1 Adding New Canonical Codes

**Process:**
1. Product/BI team identifies need for new channel code (e.g., new marketing platform)
2. Determine canonical `code`, `family`, `is_paid`, and `display_name`
3. Create Alembic migration to `INSERT` new code into `channel_taxonomy`
4. Update `channel_mapping.yaml` with vendor-to-canonical mappings
5. Update this contract document (Section 1.2 table)
6. Deploy migration and mapping file together
7. Verify FK constraints still enforced (run `validate_channel_fks.py`)

**Review Required:** Attribution service lead + Data governance team

### 5.2 Deprecating Canonical Codes

**Process:**
1. Verify zero active events/allocations use the code (query historical data)
2. Set `is_active = false` in `channel_taxonomy` (soft deprecation)
3. Update documentation to mark code as deprecated
4. After retention period (e.g., 2 years), consider hard deletion via migration

**Critical Rule:** Never delete a taxonomy code that is referenced by existing events or allocations (FK constraint will prevent this)

### 5.3 Updating Vendor Mappings

**Process:**
1. Identify new vendor channel indicators or mapping errors
2. Update `channel_mapping.yaml` with corrected/new mappings
3. Deploy updated YAML file (no migration required)
4. Verify `normalize_channel()` tests pass with new mappings
5. (Optional) Backfill historical data if mapping correction affects significant revenue

**Frequency:** As needed (reactive to new vendors, proactive based on `unmapped_channel` metrics)

---

## 6. Integration Points

### 6.1 B0.4 Ingestion Service

**Responsibility:**
- Read `channel_mapping.yaml` on service startup
- Call `normalize_channel()` for every incoming event
- Persist only canonical channel codes to `attribution_events.channel`
- Log unmapped channels and emit metrics

**Contract Requirement:**
- MUST NOT bypass `normalize_channel()` for any event
- MUST handle `'unknown'` return value gracefully (it's a valid canonical code)

### 6.2 B2.1 Attribution Engine

**Responsibility:**
- Read `attribution_events.channel` (guaranteed canonical by FK)
- Create allocations with `channel_code` set to event's canonical channel
- Process `'unknown'` channel like any other channel (no special-casing for revenue allocation)

**Contract Requirement:**
- MUST NOT attempt to "re-normalize" or override event channel values
- MUST treat `'unknown'` as valid for all attribution model calculations

### 6.3 Reporting & Dashboards

**Responsibility:**
- Query `attribution_events` and `attribution_allocations` using canonical `channel`/`channel_code`
- Display `'unknown'` as "Unknown / Unclassified" in UI
- Highlight high `'unknown'` rates as data quality warnings

**Contract Requirement:**
- MUST include `'unknown'` in all revenue/performance totals
- SHOULD provide drill-down to investigate unmapped channels

### 6.4 CI/CD Pipeline

**Responsibility:**
- Run `validate_channel_fks.py` on schema changes
- Run `validate_channel_integrity.py` on staging deployments
- Execute `test_channel_normalization.py` on every backend commit

**Contract Requirement:**
- Pipeline MUST fail if FK constraints are missing or data integrity violations exist
- Pipeline MUST fail if `normalize_channel()` tests fail

---

## 7. Appendix: Example Scenarios

### 7.1 Scenario: New Vendor Integration (Bing Ads)

**Event:** Customer connects Bing Ads account, webhook delivers event with `utm_source="bing"`, `utm_medium="cpc"`

**Expected Behavior:**
1. B0.4 ingestion calls `normalize_channel(utm_source="bing", utm_medium="cpc", vendor="bing_ads")`
2. No mapping exists in `channel_mapping.yaml` for `bing_ads` vendor
3. `normalize_channel()` returns `'unknown'`
4. `log_unmapped_channel()` logs: `vendor="bing_ads", raw_key="bing/cpc", utm_source="bing", utm_medium="cpc"`
5. Metric emitted: `unmapped_channel.count{vendor="bing_ads", raw_key="bing/cpc"}` increments
6. Event inserted with `channel='unknown'` → FK allows (no error)
7. B2.1 attribution creates allocation with `channel_code='unknown'` → FK allows (no error)
8. Reporting shows revenue under "Unknown / Unclassified" channel
9. Monitoring alert triggers if `unmapped_channel.count` exceeds threshold
10. BI team reviews logs, adds mapping to `channel_mapping.yaml`: `"bing_ads": {"BING_CPC": "bing_search_paid"}`
11. New taxonomy code `"bing_search_paid"` added via migration
12. Future Bing Ads events correctly mapped to `"bing_search_paid"`

### 7.2 Scenario: Misconfigured Campaign (Invalid UTM Parameters)

**Event:** Customer campaign has typo in `utm_source` → `utm_source="gooogle"` (extra 'o')

**Expected Behavior:**
1. B0.4 ingestion calls `normalize_channel(utm_source="gooogle", utm_medium="cpc", vendor="google_ads")`
2. Lookup in `channel_mapping.yaml` for `"google_ads"` vendor with key `"gooogle/cpc"` fails
3. `normalize_channel()` returns `'unknown'`
4. Logging captures: `vendor="google_ads", raw_key="gooogle/cpc", utm_source="gooogle"`
5. Event stored with `channel='unknown'`
6. Customer support or BI team notices spike in `'unknown'` for this customer
7. Investigation reveals typo in campaign setup
8. Customer fixes campaign URL parameters
9. Future events correctly mapped to `"google_search_paid"`
10. *No system failure* occurred; data quality issue surfaced via monitoring

### 7.3 Scenario: Legitimate Direct Traffic

**Event:** User types website URL directly into browser, no UTM parameters

**Expected Behavior:**
1. Webhook delivers event with `utm_source=None`, `utm_medium=None`
2. B0.4 ingestion calls `normalize_channel(utm_source=None, utm_medium=None, vendor="shopify")`
3. Mapping logic identifies this as direct traffic
4. `normalize_channel()` returns `'direct'` (canonical code)
5. Event inserted with `channel='direct'` → FK allows (valid canonical code)
6. No `'unknown'` logging/metrics (correctly mapped)
7. Attribution and reporting correctly attribute to "Direct" channel

---

## 8. Document Metadata

**Last Updated:** 2025-11-16  
**Version:** 1.0  
**Authors:** B0.3 Operational Integrity Commander  
**Approvers:** Attribution Service Lead, Data Governance Team  
**Related Documents:**
- Directive 69 (Channel Governance Remediation)
- `db/channel_mapping.yaml` (Vendor mapping source of truth)
- `B0.3-P_CHANNEL_GOVERNANCE_REMEDIATION.md` (Implementation evidence)

**Change History:**
- 2025-11-16: Initial version documenting channel governance contract post-remediation



