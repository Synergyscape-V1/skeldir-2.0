import type { Meta, StoryObj } from "@storybook/react";
import { useEffect, useState } from "react";
import {
  AGENT_CONFIG,
  type AgentImplementationMetadata,
  LINKS,
  REFERENCE_IMAGE_PATH,
  STORY_IDS,
  comparisonTiles,
  frameStyles,
} from "./SolutionArticulationFixtures";

const meta: Meta = {
  title: "SolutionArticulation/ComparisonGate",
  parameters: {
    layout: "fullscreen",
  },
};

export default meta;
type Story = StoryObj;

function ReferenceFrame({ src, alt }: { src: string; alt: string }) {
  const [error, setError] = useState(false);
  if (error) {
    return (
      <div style={frameStyles.stage} className="sa-frame-fallback">
        <strong>Missing reference asset</strong>
        <span>{src}</span>
      </div>
    );
  }
  return (
    <div style={frameStyles.stage}>
      <img src={src} alt={alt} style={frameStyles.media} loading="lazy" decoding="async" onError={() => setError(true)} />
    </div>
  );
}

function LiveFrame({ src, title }: { src: string; title: string }) {
  return (
    <div style={frameStyles.stage}>
      <iframe title={title} src={src} style={frameStyles.iframe} />
    </div>
  );
}

function TileCard({ title, livePath, focusPath, strategySummary }: { title: string; livePath: string; focusPath: string; strategySummary: string }) {
  return (
    <article className="sa-tile-card">
      <header className="sa-tile-header">
        <h3>{title}</h3>
        <p>{strategySummary}</p>
      </header>

      <LiveFrame src={livePath} title={`${title} live implementation`} />

      <div className="sa-action-row">
        <a href={focusPath} className="sa-action-link">
          Open {title} Focus
        </a>
      </div>
    </article>
  );
}

const metadataFieldOrder: Array<[keyof AgentImplementationMetadata, string]> = [
  ["agentId", "Agent"],
  ["strategyName", "Strategy"],
  ["cssArchitecture", "CSS architecture"],
  ["layoutMethod", "Layout methodology"],
  ["iconGraphicApproach", "Icon/graphic approach"],
  ["connectorTechnique", "Connector technique"],
  ["animationTreatment", "Animation treatment"],
  ["componentStructure", "Component structure"],
];

function FocusPanel({
  agentKey,
  title,
  mountRoot,
  metadataPath,
}: {
  agentKey: keyof typeof AGENT_CONFIG;
  title: string;
  mountRoot: string;
  metadataPath: string;
}) {
  const [metadata, setMetadata] = useState<AgentImplementationMetadata | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(metadataPath)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Metadata request failed (${response.status})`);
        }
        return response.json() as Promise<AgentImplementationMetadata>;
      })
      .then((data) => {
        if (!active) return;
        setMetadata(data);
        setMetadataError(null);
      })
      .catch((err) => {
        if (!active) return;
        setMetadata(null);
        setMetadataError(err instanceof Error ? err.message : "Unknown metadata load error");
      });
    return () => {
      active = false;
    };
  }, [metadataPath]);

  return (
    <main className="sa-focus-layout">
      <section>
        <h2>{title} - Iteration Strategy</h2>
        <p className="sa-focus-strategy">{AGENT_CONFIG[agentKey].strategySummary}</p>
      </section>
      <section>
        <h2>{title} - Implementation Metadata</h2>
        {metadata ? (
          <dl className="sa-metadata-grid">
            {metadataFieldOrder.map(([field, label]) => (
              <div key={field}>
                <dt>{label}</dt>
                <dd>{metadata[field]}</dd>
              </div>
            ))}
            <div>
              <dt>Notable decisions</dt>
              <dd>{metadata.notableDecisions.join(" | ")}</dd>
            </div>
          </dl>
        ) : (
          <p className="sa-metadata-missing">
            Missing implementation metadata at <code>{metadataPath}</code>
            {metadataError ? ` (${metadataError})` : ""}
          </p>
        )}
      </section>
      <section>
        <h2>{title} - Live Implementation</h2>
        <div className="sa-focus-frame">
          <iframe title={`${title} live implementation`} src={`${mountRoot}/index.html`} style={frameStyles.iframe} />
        </div>
      </section>
      <section>
        <h2>Reference</h2>
        <ReferenceFrame src={REFERENCE_IMAGE_PATH} alt="Reference solution articulation" />
      </section>
      <section className="sa-focus-links">
        <a href={`/?path=/story/${STORY_IDS.comparisonGrid}`}>Back to Comparison Grid</a>
        <a href={LINKS.comparisonGrid}>Open Comparison Grid (absolute URL)</a>
      </section>
      <style>{`
        .sa-focus-layout { display:grid; grid-template-columns:1fr; gap:16px; padding:20px; background:#ffffff; min-height:100vh; color:#111827; font-family:Inter, ui-sans-serif, system-ui, sans-serif; }
        .sa-focus-layout h2 { margin:0 0 8px; font-size:18px; font-weight:700; }
        .sa-focus-strategy { margin:0; font-size:14px; color:#374151; line-height:1.5; background:#eef2ff; border:1px solid #c7d2fe; border-radius:8px; padding:10px 12px; }
        .sa-metadata-grid { margin:0; display:grid; gap:10px; grid-template-columns:1fr; }
        .sa-metadata-grid div { padding:10px 12px; border:1px solid #d1d5db; border-radius:8px; background:#ffffff; }
        .sa-metadata-grid dt { font-size:12px; font-weight:700; color:#4b5563; margin-bottom:4px; }
        .sa-metadata-grid dd { margin:0; font-size:14px; color:#111827; line-height:1.35; }
        .sa-metadata-missing { margin:0; font-size:13px; color:#7f1d1d; background:#fee2e2; border:1px solid #fecaca; border-radius:8px; padding:10px 12px; }
        .sa-focus-frame { width:100%; aspect-ratio:16 / 9; border:1px solid #d1d5db; border-radius:10px; overflow:hidden; background:#fff; }
        .sa-focus-links { display:flex; gap:14px; flex-wrap:wrap; }
        .sa-focus-links a { color:#1d4ed8; font-weight:600; text-decoration:underline; }
        @media (min-width: 1280px) {
          .sa-focus-layout { grid-template-columns:1fr 1fr; align-items:start; }
          .sa-focus-layout section:nth-child(1), .sa-focus-layout section:last-child { grid-column:1 / -1; }
        }
      `}</style>
    </main>
  );
}

export const ComparisonGrid: Story = {
  render: () => (
    <main className="sa-grid-page">
      <header className="sa-grid-header">
        <h1>Solution Articulation Comparison Grid</h1>
        <p>Reference is pinned as a sticky header. Agent A-E tiles render live HTML implementations from <code>/public/implementations/</code>.</p>
        <p className="sa-grid-subtitle">Each agent tile is a coded implementation of the same reference, using a distinct technical approach.</p>
      </header>

      <section className="sa-reference-sticky">
        <h2>Reference (Pinned)</h2>
        <ReferenceFrame src={REFERENCE_IMAGE_PATH} alt="Reference solution articulation" />
      </section>

      <section className="sa-grid-wrap">
        {comparisonTiles.map((tile) => (
          <TileCard
            key={tile.key}
            title={tile.label}
            livePath={tile.livePath}
            focusPath={tile.focusStoryPath}
            strategySummary={tile.strategySummary}
          />
        ))}
      </section>

      <style>{`
        .sa-grid-page { min-height:100vh; background:#ffffff; color:#111827; padding:24px; font-family:Inter, ui-sans-serif, system-ui, sans-serif; }
        .sa-grid-header { margin-bottom:20px; }
        .sa-grid-header h1 { margin:0; font-size:28px; font-weight:800; letter-spacing:-0.02em; }
        .sa-grid-header p { margin:8px 0 0; font-size:14px; color:#374151; }
        .sa-grid-subtitle { font-weight:600; color:#1f2937; }
        .sa-grid-header code { background:#e5e7eb; border-radius:6px; padding:2px 6px; margin-left:4px; font-size:13px; }
        .sa-reference-sticky { position:sticky; top:0; z-index:2; background:#ffffff; padding:10px 0 14px; margin-bottom:16px; border-bottom:1px solid #dbe3ee; }
        .sa-reference-sticky h2 { margin:0 0 8px; font-size:16px; font-weight:800; }
        .sa-grid-wrap { display:grid; gap:16px; grid-template-columns:1fr; }
        .sa-tile-card { border:1px solid #d1d5db; border-radius:12px; background:#ffffff; padding:12px; box-shadow:0 1px 4px rgba(17,24,39,0.07); }
        .sa-tile-header h3 { margin:0 0 6px; font-size:18px; font-weight:700; }
        .sa-tile-header p { margin:0 0 10px; font-size:12px; color:#4b5563; line-height:1.45; }
        .sa-frame-fallback { display:flex; flex-direction:column; justify-content:center; align-items:center; gap:6px; text-align:center; padding:12px; color:#111827; background:#f3f4f6; font-size:12px; }
        .sa-frame-fallback span { color:#4b5563; word-break:break-all; }
        .sa-action-row { margin-top:10px; display:flex; align-items:center; min-height:32px; }
        .sa-action-link { display:inline-flex; align-items:center; justify-content:center; padding:6px 10px; border-radius:8px; border:1px solid #2563eb; color:#1d4ed8; text-decoration:none; font-size:13px; font-weight:700; }
        .sa-action-link:hover { background:#eff6ff; }
        @media (min-width:768px) and (max-width:1279px) { .sa-grid-wrap { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
        @media (min-width:1280px) { .sa-grid-wrap { grid-template-columns:repeat(3, minmax(0, 1fr)); } }
      `}</style>
    </main>
  ),
};

export const AgentA_Focus: Story = {
  name: "Agent A - Vanilla CSS + Grid + Inline SVG",
  render: () => (
    <FocusPanel
      agentKey="agent-a"
      title={AGENT_CONFIG["agent-a"].label}
      mountRoot={AGENT_CONFIG["agent-a"].mountRoot}
      metadataPath={AGENT_CONFIG["agent-a"].metadataPath}
    />
  ),
};
export const AgentB_Focus: Story = {
  name: "Agent B - Utility/Tailwind-style + Flex + Pseudo Connectors",
  render: () => (
    <FocusPanel
      agentKey="agent-b"
      title={AGENT_CONFIG["agent-b"].label}
      mountRoot={AGENT_CONFIG["agent-b"].mountRoot}
      metadataPath={AGENT_CONFIG["agent-b"].metadataPath}
    />
  ),
};
export const AgentC_Focus: Story = {
  name: "Agent C - CSS Modules-style + Hybrid Layout + SVG Sprite",
  render: () => (
    <FocusPanel
      agentKey="agent-c"
      title={AGENT_CONFIG["agent-c"].label}
      mountRoot={AGENT_CONFIG["agent-c"].mountRoot}
      metadataPath={AGENT_CONFIG["agent-c"].metadataPath}
    />
  ),
};
export const AgentD_Focus: Story = {
  name: "Agent D - Styled-components-style + Canvas Flow Connector",
  render: () => (
    <FocusPanel
      agentKey="agent-d"
      title={AGENT_CONFIG["agent-d"].label}
      mountRoot={AGENT_CONFIG["agent-d"].mountRoot}
      metadataPath={AGENT_CONFIG["agent-d"].metadataPath}
    />
  ),
};
export const AgentE_Focus: Story = {
  name: "Agent E - Emotion-style CSS-in-JS + Clip-path/Borders",
  render: () => (
    <FocusPanel
      agentKey="agent-e"
      title={AGENT_CONFIG["agent-e"].label}
      mountRoot={AGENT_CONFIG["agent-e"].mountRoot}
      metadataPath={AGENT_CONFIG["agent-e"].metadataPath}
    />
  ),
};
