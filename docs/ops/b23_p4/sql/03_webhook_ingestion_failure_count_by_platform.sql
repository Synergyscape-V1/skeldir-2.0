-- B2.3-P4 canonical SQL telemetry: webhook ingestion failures by platform.
-- Parameters: :tenant_id UUID.
SELECT
    provider AS platform,
    count(*)::integer AS failure_count
FROM public.b23_webhook_ingestion_logs
WHERE tenant_id = :tenant_id
  AND ingestion_status = 'failed'
  AND received_at >= now() - interval '24 hours'
GROUP BY provider
ORDER BY provider;
