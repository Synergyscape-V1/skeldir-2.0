#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <runtime_db_url> <runtime_probe_json> <output_dir>"
  exit 1
fi

DB_URL="$1"
PROBE_JSON="$2"
OUT_DIR="$3"
SQL_DIR="docs/ops/llm_p4/sql"

mkdir -p "$OUT_DIR"

if [[ ! -f "$PROBE_JSON" ]]; then
  echo "Runtime probe JSON not found: $PROBE_JSON"
  exit 1
fi

TENANT_ID=$(python -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['tenant_id'])" "$PROBE_JSON")
USER_ID=$(python -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['primary_user_id'])" "$PROBE_JSON")
BREAKER_USER_ID=$(python -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['breaker_user_id'])" "$PROBE_JSON")
SHUTOFF_USER_ID=$(python -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['shutoff_user_id'])" "$PROBE_JSON")

run_query() {
  local sql_file="$1"
  local out_file="$2"
  local user_id="$3"
  local wrapper_file
  wrapper_file="$(mktemp)"

  cat > "$wrapper_file" <<SQL
SET app.current_tenant_id = :'tenant_id';
SET app.current_user_id = :'user_id';
\i $sql_file
SQL

  psql "$DB_URL" \
    -v ON_ERROR_STOP=1 \
    -v tenant_id="$TENANT_ID" \
    -v user_id="$user_id" \
    -f "$wrapper_file" \
    --csv | awk '$0 != "SET"' > "$out_file"

  rm -f "$wrapper_file"
}

run_query "$SQL_DIR/01_monthly_spend.sql" "$OUT_DIR/01_monthly_spend.csv" "$USER_ID"
run_query "$SQL_DIR/02_cache_hit_rate.sql" "$OUT_DIR/02_cache_hit_rate.csv" "$USER_ID"
run_query "$SQL_DIR/04_provider_cost_latency_distribution.sql" "$OUT_DIR/04_provider_cost_latency_distribution.csv" "$USER_ID"

breaker_tmp="$(mktemp)"
shutoff_tmp="$(mktemp)"
run_query "$SQL_DIR/03_breaker_shutoff_state.sql" "$breaker_tmp" "$BREAKER_USER_ID"
run_query "$SQL_DIR/03_breaker_shutoff_state.sql" "$shutoff_tmp" "$SHUTOFF_USER_ID"
head -n 1 "$breaker_tmp" > "$OUT_DIR/03_breaker_shutoff_state.csv"
tail -n +2 "$breaker_tmp" >> "$OUT_DIR/03_breaker_shutoff_state.csv"
tail -n +2 "$shutoff_tmp" >> "$OUT_DIR/03_breaker_shutoff_state.csv"
rm -f "$breaker_tmp" "$shutoff_tmp"

for csv in "$OUT_DIR"/*.csv; do
  if [[ $(wc -l < "$csv") -le 1 ]]; then
    echo "Dashboard output is empty: $csv"
    exit 1
  fi
done

head -n 1 "$OUT_DIR/01_monthly_spend.csv" | grep -q "tenant_id,user_id,month,total_cost_cents,total_calls"
head -n 1 "$OUT_DIR/02_cache_hit_rate.csv" | grep -q "endpoint,total_calls,cache_hits,cache_hit_rate_pct"
head -n 1 "$OUT_DIR/03_breaker_shutoff_state.csv" | grep -q "state_type,tenant_id,user_id,state_key,state_value,failure_count,opened_at,updated_at"
head -n 1 "$OUT_DIR/04_provider_cost_latency_distribution.csv" | grep -q "provider,model,status,call_count,total_cost_cents,min_latency_ms,avg_latency_ms,max_latency_ms"

echo "B0.7-P4 operational dashboard queries completed: $OUT_DIR"
