import type { DashboardStageAsset } from "@/components/layout/dashboardStagePhysics";
import { DASHBOARD_STAGE_STYLES } from "@/components/layout/dashboardStagePhysics";

type DashboardStageProps = {
  asset: DashboardStageAsset;
  className?: string;
  imageClassName?: string;
  loading?: "lazy" | "eager";
  fetchPriority?: "high" | "low" | "auto";
};

export function DashboardStage({
  asset,
  className = "",
  imageClassName = "demo-dashboard-image",
  loading = "lazy",
  fetchPriority,
}: DashboardStageProps) {
  const containerClass = className
    ? `demo-image-container ${className}`
    : "demo-image-container";

  return (
    <>
      <div className={containerClass}>
        <div className="demo-image-float-wrapper">
          <div className="demo-image-glass">
            <img
              src={asset.src}
              alt={asset.alt}
              className={imageClassName}
              width={asset.width}
              height={asset.height}
              loading={loading}
              decoding="async"
              {...(fetchPriority ? { fetchPriority } : {})}
            />
          </div>
        </div>
      </div>
      <style>{DASHBOARD_STAGE_STYLES}</style>
    </>
  );
}
