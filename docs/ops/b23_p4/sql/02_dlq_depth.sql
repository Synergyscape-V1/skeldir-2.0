-- B2.3-P4 canonical SQL telemetry: durable worker DLQ depth.
-- Parameters: :tenant_id UUID.
SELECT
    COALESCE(sum(depth), 0)::integer AS dlq_depth
FROM (
    SELECT count(*) AS depth
    FROM public.worker_failed_jobs
    WHERE status IN ('pending', 'in_progress')
      AND tenant_id = :tenant_id
    UNION ALL
    SELECT count(*) AS depth
    FROM public.worker_failed_jobs
    WHERE status IN ('pending', 'in_progress')
      AND tenant_id IS NULL
) AS dlq_counts;
