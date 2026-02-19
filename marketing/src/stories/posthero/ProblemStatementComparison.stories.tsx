import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { ProblemStatementCanonical } from "../../components/layout/iterations/ProblemStatement.canonical";

const REFERENCE_IMAGE = "/implementations/reference/problem-articulation-final.jpg";

const meta: Meta = {
  title: "Posthero/ProblemStatementCanonical",
  parameters: {
    layout: "fullscreen",
  },
};

export default meta;

type Story = StoryObj;

function ReferenceFrame() {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div
        style={{
          aspectRatio: "16/9",
          background: "#f3f4f6",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          color: "#6b7280",
          fontSize: "12px",
          padding: "16px",
        }}
      >
        <strong>Missing reference asset</strong>
        <span>{REFERENCE_IMAGE}</span>
        <span>Mount reference at /public/implementations/reference/ before review.</span>
      </div>
    );
  }
  return (
    <img
      src={REFERENCE_IMAGE}
      alt="Reference problem articulation"
      style={{
        width: "100%",
        aspectRatio: "16/9",
        objectFit: "cover",
        objectPosition: "top center",
        display: "block",
      }}
      onError={() => setFailed(true)}
    />
  );
}

export const Canonical: Story = {
  render: () => <ProblemStatementCanonical />,
};

export const ComparisonGrid: Story = {
  render: () => (
    <main
      style={{
        minHeight: "100vh",
        background: "#f8fafc",
        padding: "24px",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
        gap: "24px",
        alignItems: "start",
      }}
    >
      <section
        style={{
          border: "1px solid #d1d5db",
          borderRadius: "12px",
          overflow: "hidden",
          background: "#fff",
        }}
      >
        <header style={{ padding: "12px 16px", borderBottom: "1px solid #e5e7eb" }}>
          <h3 style={{ margin: 0, fontSize: "18px", fontWeight: 700 }}>Reference</h3>
          <p style={{ margin: "4px 0 0", fontSize: "12px", color: "#6b7280" }}>
            Design spec / source of truth
          </p>
        </header>
        <ReferenceFrame />
      </section>
      <section
        style={{
          border: "1px solid #d1d5db",
          borderRadius: "12px",
          overflow: "hidden",
          background: "#fff",
        }}
      >
        <header style={{ padding: "12px 16px", borderBottom: "1px solid #e5e7eb" }}>
          <h3 style={{ margin: 0, fontSize: "18px", fontWeight: 700 }}>Canonical</h3>
          <p style={{ margin: "4px 0 0", fontSize: "12px", color: "#6b7280" }}>
            Live implementation
          </p>
        </header>
        <div style={{ padding: 0 }}>
          <ProblemStatementCanonical />
        </div>
      </section>
    </main>
  ),
};
