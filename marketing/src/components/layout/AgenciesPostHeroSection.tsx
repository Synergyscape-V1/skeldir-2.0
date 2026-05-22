"use client";

import { PostHeroValidation } from "@/components/layout/PostHeroValidation";

export function AgenciesPostHeroSection() {
  return (
    <section
      className="agencies-posthero"
      style={{
        width: "100%",
        padding: 0,
        margin: 0,
      }}
    >
      {/* Full-bleed: do NOT constrain to a fixed container width */}
      <PostHeroValidation />
    </section>
  );
}
