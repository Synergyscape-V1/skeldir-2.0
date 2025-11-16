# Channel Monitoring Integration Guide

**Version:** 1.0  
**Status:** Implementation Guide  
**Ownership:** Platform Engineering, Attribution Service  
**Related:** db/docs/channel_contract.md, B0.3-P_CHANNEL_GOVERNANCE_REMEDIATION.md

---

## 1. Overview

This document specifies the monitoring and observability integration for channel governance. It defines metrics, alerts, and dashboards required to maintain data quality and detect mapping gaps proactively.

**Primary Goals:**
- Real-time visibility into unmapped channel occurrences
- Proactive alerting on data quality degradation
- Actionable dashboards for investigating mapping gaps
- Historical tracking of channel governance health

---

## 2. Metrics Specification

### 2.1 Unmapped Channel Counter

**Metric Name:** `unmapped_channel.count`  
**Type:** Counter  
**Description:** Incremented every time `normalize_channel()` returns `'unknown'` due to unmapped vendor indicators

**Tags:**
- `vendor` (string): Vendor/integration identifier (e.g., `"google_ads"`, `"shopify"`, `"bing_ads"`)
- `raw_key` (string): The combined key used for mapping lookup (e.g., `"bing_ads/bing/cpc"`)
- `tenant_id` (string, optional): Tenant experiencing the unmapped channel

**Implementation Location:**
```python
# backend/app/ingestion/channel_normalization.py
def increment_unmapped_channel_metric(vendor: str, raw_key: str) -> None:
    # Current: logs at DEBUG level
    # TODO: Emit to Prometheus/Datadog/CloudWatch
    pass
```

**Prometheus Format:**
```promql
# Counter metric
unmapped_channel_count{vendor="bing_ads", raw_key="bing_ads/bing/cpc", tenant_id="abc123"}
```

**CloudWatch Format:**
```json
{
  "MetricName": "UnmappedChannelCount",
  "Dimensions": [
    {"Name": "Vendor", "Value": "bing_ads"},
    {"Name": "RawKey", "Value": "bing_ads/bing/cpc"},
    {"Name": "TenantId", "Value": "abc123"}
  ],
  "Value": 1,
  "Unit": "Count"
}
```

---

### 2.2 Unmapped Channel Ratio

**Metric Name:** `unmapped_channel_ratio`  
**Type:** Gauge (percentage)  
**Description:** Percentage of events with `channel='unknown'` over total events, calculated per tenant and globally

**Tags:**
- `tenant_id` (string): Tenant identifier (or `"global"` for cross-tenant aggregate)
- `time_window` (string): Time window for calculation (e.g., `"1h"`, `"24h"`, `"7d"`)

**Calculation:**
```sql
-- Per-tenant calculation
SELECT 
    tenant_id,
    (COUNT(*) FILTER (WHERE channel = 'unknown') * 100.0 / COUNT(*)) AS unmapped_ratio
FROM attribution_events
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY tenant_id;

-- Global calculation
SELECT 
    (COUNT(*) FILTER (WHERE channel = 'unknown') * 100.0 / COUNT(*)) AS unmapped_ratio
FROM attribution_events
WHERE created_at > NOW() - INTERVAL '24 hours';
```

**Update Frequency:** Calculated periodically (e.g., every 5 minutes) via scheduled query or materialized view

**Prometheus Format:**
```promql
# Gauge metric (percentage)
unmapped_channel_ratio{tenant_id="abc123", time_window="24h"} 2.5
unmapped_channel_ratio{tenant_id="global", time_window="24h"} 1.2
```

---

### 2.3 Channel Normalization Latency

**Metric Name:** `channel_normalization.duration_ms`  
**Type:** Histogram  
**Description:** Time taken to execute `normalize_channel()` function, for performance monitoring

**Tags:**
- `result_type` (string): `"mapped"` or `"unmapped"` (whether mapping was found)

**Percentiles:** p50, p95, p99

**Prometheus Format:**
```promql
# Histogram metric
channel_normalization_duration_ms_bucket{result_type="mapped", le="1"} 1000
channel_normalization_duration_ms_bucket{result_type="mapped", le="5"} 1500
channel_normalization_duration_ms_bucket{result_type="mapped", le="+Inf"} 1600
```

---

### 2.4 Channel Taxonomy Size

**Metric Name:** `channel_taxonomy.code_count`  
**Type:** Gauge  
**Description:** Total number of canonical channel codes in `channel_taxonomy` table

**Tags:**
- `is_active` (boolean): Whether counting active codes only

**Calculation:**
```sql
SELECT COUNT(*) FROM channel_taxonomy WHERE is_active = true;
```

**Update Frequency:** After schema migrations or on-demand

---

## 3. Alert Definitions

### 3.1 High Unmapped Channel Ratio (Per-Tenant)

**Alert Name:** `ChannelGovernance_HighUnmappedRatio_Tenant`  
**Severity:** WARNING  
**Condition:** `unmapped_channel_ratio{tenant_id!="global", time_window="7d"} > 5`  
**Duration:** 30 minutes (sustained)  
**Description:** A single tenant has > 5% of events with unmapped channels over the last 7 days

**Actions:**
- Create internal ticket in issue tracker
- Notify customer success team with tenant_id
- Review logs for specific unmapped raw_key values

**Prometheus Alert Rule:**
```yaml
- alert: ChannelGovernance_HighUnmappedRatio_Tenant
  expr: unmapped_channel_ratio{tenant_id!="global", time_window="7d"} > 5
  for: 30m
  labels:
    severity: warning
    team: attribution
  annotations:
    summary: "High unmapped channel ratio for tenant {{ $labels.tenant_id }}"
    description: "Tenant {{ $labels.tenant_id }} has {{ $value }}% unmapped channels over 7 days (threshold: 5%)"
    runbook_url: "https://docs.skeldir.io/runbooks/unmapped-channels"
```

---

### 3.2 Critical Unmapped Channel Ratio (Per-Tenant)

**Alert Name:** `ChannelGovernance_CriticalUnmappedRatio_Tenant`  
**Severity:** ERROR  
**Condition:** `unmapped_channel_ratio{tenant_id!="global", time_window="7d"} > 10`  
**Duration:** 15 minutes (sustained)  
**Description:** A single tenant has > 10% of events with unmapped channels over the last 7 days

**Actions:**
- Create high-priority incident ticket
- Notify customer success and attribution service lead
- Escalate for immediate mapping investigation

**Prometheus Alert Rule:**
```yaml
- alert: ChannelGovernance_CriticalUnmappedRatio_Tenant
  expr: unmapped_channel_ratio{tenant_id!="global", time_window="7d"} > 10
  for: 15m
  labels:
    severity: error
    team: attribution
    escalation: true
  annotations:
    summary: "CRITICAL: Very high unmapped channel ratio for tenant {{ $labels.tenant_id }}"
    description: "Tenant {{ $labels.tenant_id }} has {{ $value }}% unmapped channels over 7 days (threshold: 10%)"
    runbook_url: "https://docs.skeldir.io/runbooks/unmapped-channels"
```

---

### 3.3 New Vendor Detected

**Alert Name:** `ChannelGovernance_NewVendorDetected`  
**Severity:** INFO  
**Condition:** `increase(unmapped_channel_count{vendor!~"google_ads|facebook_ads|shopify|stripe|paypal|woocommerce|tiktok_ads"}[1h]) > 0`  
**Description:** A new vendor (not in current mapping) has been detected

**Actions:**
- Notify BI/data team
- Review vendor identifier and prepare mapping update

**Prometheus Alert Rule:**
```yaml
- alert: ChannelGovernance_NewVendorDetected
  expr: increase(unmapped_channel_count{vendor!~"google_ads|facebook_ads|shopify|stripe|paypal|woocommerce|tiktok_ads"}[1h]) > 0
  labels:
    severity: info
    team: bi
  annotations:
    summary: "New vendor detected: {{ $labels.vendor }}"
    description: "New vendor '{{ $labels.vendor }}' with raw_key '{{ $labels.raw_key }}' has unmapped channels"
    runbook_url: "https://docs.skeldir.io/runbooks/new-vendor-mapping"
```

---

### 3.4 Unmapped Channel Spike

**Alert Name:** `ChannelGovernance_UnmappedChannelSpike`  
**Severity:** WARNING  
**Condition:** `rate(unmapped_channel_count[5m]) > 10`  
**Duration:** 10 minutes  
**Description:** Sudden spike in unmapped channel occurrences (> 10 per minute)

**Actions:**
- Investigate recent integration changes
- Check for customer campaign misconfigurations

**Prometheus Alert Rule:**
```yaml
- alert: ChannelGovernance_UnmappedChannelSpike
  expr: rate(unmapped_channel_count[5m]) > 10
  for: 10m
  labels:
    severity: warning
    team: attribution
  annotations:
    summary: "Spike in unmapped channels detected"
    description: "Unmapped channel rate is {{ $value }} per second (threshold: 10/min)"
    runbook_url: "https://docs.skeldir.io/runbooks/unmapped-channels-spike"
```

---

## 4. Dashboard Specifications

### 4.1 Channel Governance Health Dashboard

**Dashboard Name:** Channel Governance Health  
**Purpose:** Overall health monitoring of channel governance system

**Panels:**

1. **Unmapped Channel Ratio (Global)**
   - Visualization: Time series (line chart)
   - Metric: `unmapped_channel_ratio{tenant_id="global"}`
   - Time range: Last 30 days
   - Threshold lines: 5% (warning), 10% (critical)

2. **Unmapped Channel Ratio by Tenant**
   - Visualization: Table (sorted by ratio descending)
   - Metric: `unmapped_channel_ratio{tenant_id!="global", time_window="7d"}`
   - Columns: Tenant ID, Unmapped Ratio (%), Event Count, Status
   - Highlight: Rows > 5% in yellow, > 10% in red

3. **Unmapped Channels by Vendor**
   - Visualization: Bar chart (horizontal)
   - Metric: `increase(unmapped_channel_count[24h])` grouped by `vendor`
   - Top 10 vendors by unmapped count

4. **Unmapped Channels by Raw Key**
   - Visualization: Table
   - Metric: `increase(unmapped_channel_count[24h])` grouped by `raw_key`
   - Columns: Raw Key, Vendor, Count (24h), Action (link to mapping update)
   - Top 20 raw keys

5. **Channel Taxonomy Size**
   - Visualization: Single stat
   - Metric: `channel_taxonomy.code_count{is_active="true"}`
   - Display: Current count + trend over last 30 days

6. **Normalization Performance**
   - Visualization: Time series (multiple lines)
   - Metrics: 
     - `histogram_quantile(0.50, channel_normalization_duration_ms)` (p50)
     - `histogram_quantile(0.95, channel_normalization_duration_ms)` (p95)
     - `histogram_quantile(0.99, channel_normalization_duration_ms)` (p99)

---

### 4.2 Unmapped Channels Investigation Dashboard

**Dashboard Name:** Unmapped Channels Investigation  
**Purpose:** Detailed drill-down for investigating specific unmapped occurrences

**Panels:**

1. **Unmapped Channel Timeline**
   - Visualization: Time series (stacked area)
   - Metric: `increase(unmapped_channel_count[1h])` grouped by `vendor`
   - Time range: Configurable (default: last 7 days)

2. **Top Unmapped Raw Keys**
   - Visualization: Table (sortable, filterable)
   - Columns: Raw Key, Vendor, Count, First Seen, Last Seen, Example Tenant
   - Data source: Aggregated from logs

3. **Per-Vendor Breakdown**
   - Visualization: Pie chart
   - Metric: `sum(increase(unmapped_channel_count[24h])) by (vendor)`

4. **Tenant-Specific Drill-Down**
   - Visualization: Table (filterable by tenant_id)
   - Columns: Tenant ID, Unmapped Count, Unmapped Ratio, Top Raw Keys
   - Link: Click tenant to view detailed logs

---

### 4.3 Channel Performance Dashboard (Integration)

**Dashboard Name:** Channel Performance (Extended)  
**Purpose:** Integrate unmapped channel visibility into existing channel performance dashboard

**New Panels:**

1. **Revenue by Channel (Including Unknown)**
   - Visualization: Bar chart
   - Query:
     ```sql
     SELECT 
         channel,
         SUM(allocated_revenue_cents) / 100.0 AS total_revenue
     FROM attribution_allocations
     WHERE created_at > NOW() - INTERVAL '30 days'
     GROUP BY channel
     ORDER BY total_revenue DESC;
     ```
   - Highlight: 'unknown' channel bar in orange to distinguish from legitimate channels

2. **Unknown Channel Revenue Trend**
   - Visualization: Time series
   - Query:
     ```sql
     SELECT 
         DATE_TRUNC('day', created_at) AS date,
         SUM(allocated_revenue_cents) / 100.0 AS unknown_revenue
     FROM attribution_allocations
     WHERE channel_code = 'unknown'
     GROUP BY date
     ORDER BY date;
     ```
   - Purpose: Track financial impact of unmapped channels

---

## 5. Log Integration

### 5.1 Structured Logging Requirements

All unmapped channel occurrences are logged via `log_unmapped_channel()` function.

**Log Level:** INFO  
**Log Format:** JSON (structured logging)

**Required Fields:**
```json
{
  "timestamp": "2025-11-16T12:34:56.789Z",
  "level": "INFO",
  "event_type": "unmapped_channel",
  "service": "attribution-ingestion",
  "raw_key": "bing_ads/bing/cpc",
  "utm_source": "bing",
  "utm_medium": "cpc",
  "vendor": "bing_ads",
  "tenant_id": "abc123",
  "fallback_channel": "unknown",
  "function": "normalize_channel",
  "file": "channel_normalization.py",
  "line": 234
}
```

### 5.2 Log Aggregation

**Platform:** ELK Stack / CloudWatch Logs / Datadog Logs  
**Index Pattern:** `skeldir-attribution-*` or equivalent  
**Retention:** 90 days (configurable)

**Recommended Queries:**

1. **Top Unmapped Raw Keys (Last 24h)**
   ```
   event_type:"unmapped_channel" AND @timestamp:[now-24h TO now]
   | stats count by raw_key
   | sort -count
   | head 20
   ```

2. **Unmapped Channels by Tenant**
   ```
   event_type:"unmapped_channel" AND @timestamp:[now-7d TO now]
   | stats count by tenant_id
   | sort -count
   ```

3. **New Vendors (Last 30 days)**
   ```
   event_type:"unmapped_channel" AND @timestamp:[now-30d TO now]
   | stats dc(vendor) as unique_vendors, count by vendor
   | where unique_vendors = 1 AND count < 100
   ```

---

## 6. Implementation Checklist

### 6.1 Backend Implementation

- [ ] Update `increment_unmapped_channel_metric()` to emit to monitoring platform
- [ ] Add Prometheus exporter or CloudWatch client to ingestion service
- [ ] Implement `unmapped_channel_ratio` calculation (scheduled query or MV)
- [ ] Add `channel_normalization.duration_ms` histogram instrumentation
- [ ] Verify structured logging is enabled and configured

### 6.2 Monitoring Platform Configuration

- [ ] Create Prometheus scrape config for attribution service
- [ ] Define alert rules in Prometheus/Alertmanager
- [ ] Configure notification channels (Slack, PagerDuty, email)
- [ ] Set up alert routing by severity

### 6.3 Dashboard Creation

- [ ] Create "Channel Governance Health" dashboard
- [ ] Create "Unmapped Channels Investigation" dashboard
- [ ] Extend existing "Channel Performance" dashboard with 'unknown' visibility
- [ ] Share dashboards with attribution team, BI team, customer success

### 6.4 Operational Procedures

- [ ] Document runbook for responding to unmapped channel alerts
- [ ] Define escalation paths for high/critical unmapped ratios
- [ ] Create process for adding new vendor mappings
- [ ] Schedule weekly review of unmapped channel metrics

---

## 7. Monitoring Platform Examples

### 7.1 Prometheus + Grafana

**metrics.py (Prometheus Client):**
```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
unmapped_channel_counter = Counter(
    'unmapped_channel_count',
    'Count of unmapped channel occurrences',
    ['vendor', 'raw_key', 'tenant_id']
)

channel_normalization_duration = Histogram(
    'channel_normalization_duration_ms',
    'Channel normalization function duration',
    ['result_type'],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
)

# Usage in channel_normalization.py
def increment_unmapped_channel_metric(vendor: str, raw_key: str, tenant_id: str = None):
    unmapped_channel_counter.labels(
        vendor=vendor,
        raw_key=raw_key,
        tenant_id=tenant_id or 'unknown'
    ).inc()
```

### 7.2 AWS CloudWatch

**cloudwatch.py (Boto3 Client):**
```python
import boto3
from datetime import datetime

cloudwatch = boto3.client('cloudwatch')

def increment_unmapped_channel_metric(vendor: str, raw_key: str, tenant_id: str = None):
    cloudwatch.put_metric_data(
        Namespace='Skeldir/Attribution',
        MetricData=[
            {
                'MetricName': 'UnmappedChannelCount',
                'Dimensions': [
                    {'Name': 'Vendor', 'Value': vendor},
                    {'Name': 'RawKey', 'Value': raw_key},
                    {'Name': 'TenantId', 'Value': tenant_id or 'unknown'},
                ],
                'Value': 1.0,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            }
        ]
    )
```

### 7.3 Datadog

**datadog.py (Datadog Client):**
```python
from datadog import statsd

def increment_unmapped_channel_metric(vendor: str, raw_key: str, tenant_id: str = None):
    statsd.increment(
        'skeldir.attribution.unmapped_channel.count',
        tags=[
            f'vendor:{vendor}',
            f'raw_key:{raw_key}',
            f'tenant_id:{tenant_id or "unknown"}',
        ]
    )
```

---

## 8. Document Metadata

**Last Updated:** 2025-11-16  
**Version:** 1.0  
**Authors:** B0.3 Operational Integrity Commander, Platform Engineering  
**Approvers:** Attribution Service Lead, SRE Lead  
**Related Documents:**
- db/docs/channel_contract.md (Section 3: Data Quality Strategy)
- B0.3-P_CHANNEL_GOVERNANCE_REMEDIATION.md (Phase 6 implementation)
- Skeldir Runbook: Unmapped Channels (https://docs.skeldir.io/runbooks/unmapped-channels)

**Change History:**
- 2025-11-16: Initial version documenting monitoring integration for channel governance



