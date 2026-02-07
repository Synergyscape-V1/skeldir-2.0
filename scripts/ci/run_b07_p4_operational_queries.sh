#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <runtime_db_url> <runtime_probe_json> <output_dir>"
  exit 1
fi

DB_URL="$1"
PROBE_JSON="$2"
OUT_DIR="$3"
SQL_DIR="docs/ops/b07_p4/sql"

mkdir -p "$OUT_DIR"

if [[ ! -f "$PROBE_JSON" ]]; then
  echo "Runtime probe JSON not found: $PROBE_JSON"
  exit 1
fi

TENANT_ID=$(python -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['tenant_id'])" "$PROBE_JSON")
USER_ID=$(python -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['primary_user_id'])" "$PROBE_JSON")

run_query() {
  local sql_file="$1"
  local out_file="$2"
  psql "$DB_URL" \
    -v ON_ERROR_STOP=1 \
    -v tenant_id="$TENANT_ID" \
    -v user_id="$USER_ID" \
    -f "$sql_file" \
    --csv > "$out_file"
}

run_query "$SQL_DIR/01_monthly_spend.sql" "$OUT_DIR/01_monthly_spend.csv"
run_query "$SQL_DIR/02_cache_hit_rate.sql" "$OUT_DIR/02_cache_hit_rate.csv"
run_query "$SQL_DIR/03_breaker_shutoff_state.sql" "$OUT_DIR/03_breaker_shutoff_state.csv"
run_query "$SQL_DIR/04_provider_cost_latency_distribution.sql" "$OUT_DIR/04_provider_cost_latency_distribution.csv"

for csv in "$OUT_DIR"/*.csv; do
  if [[ $(wc -l < "$csv") -le 1 ]]; then
    echo "Dashboard output is empty: $csv"
    exit 1
  fi
done

grep -q "tenant_id,user_id,month,total_cost_cents,total_calls" "$OUT_DIR/01_monthly_spend.csv"
grep -q "endpoint,total_calls,cache_hits,cache_hit_rate_pct" "$OUT_DIR/02_cache_hit_rate.csv"
grep -q "state_type,tenant_id,user_id,state_key,state_value,failure_count,opened_at,updated_at" "$OUT_DIR/03_breaker_shutoff_state.csv"
grep -q "provider,model,status,call_count,total_cost_cents,min_latency_ms,avg_latency_ms,max_latency_ms" "$OUT_DIR/04_provider_cost_latency_distribution.csv"

echo "B0.7-P4 operational dashboard queries completed: $OUT_DIR"
