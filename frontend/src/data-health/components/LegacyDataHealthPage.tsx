import React from "react";
import { useNavigate } from "react-router-dom";

export function LegacyDataHealthPage() {
  const navigate = useNavigate();

  return (
    <main style={{ padding: 24, fontFamily: "Segoe UI, sans-serif", display: "grid", gap: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0, fontSize: 34 }}>Data Health</h1>
        <button
          type="button"
          onClick={() => navigate("/data/integrations")}
          style={{
            minWidth: 44,
            minHeight: 44,
            borderRadius: 8,
            border: "1px solid var(--dh-border-default)",
            background: "var(--dh-bg-primary)",
            padding: "10px 14px",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          View Platform Status
        </button>
      </header>

      <section style={{ border: "1px solid var(--dh-border-default)", borderRadius: 10, background: "var(--dh-bg-primary)", padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Current Runtime Dashboard</h2>
        <p style={{ marginBottom: 0 }}>
          The live <code>/data</code> route is intentionally kept separate from the five design iterations while comparison is in progress.
        </p>
      </section>

      <section style={{ border: "1px solid var(--dh-border-default)", borderRadius: 10, background: "var(--dh-bg-primary)", padding: 16 }}>
        <h3 style={{ marginTop: 0 }}>Comparison Workflow</h3>
        <ol style={{ marginBottom: 0 }}>
          <li>Review all five implementations in Storybook.</li>
          <li>Select a winner using the comparison scorecard.</li>
          <li>Promote only the chosen iteration into production runtime.</li>
        </ol>
      </section>
    </main>
  );
}
