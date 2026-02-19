import type { CSSProperties } from "react";

export type AgentKey = "agent-a" | "agent-b" | "agent-c" | "agent-d" | "agent-e";

export type AgentImplementationMetadata = {
  agentId: "A" | "B" | "C" | "D" | "E";
  strategyName: string;
  cssArchitecture: string;
  layoutMethod: string;
  iconGraphicApproach: string;
  connectorTechnique: string;
  animationTreatment: string;
  componentStructure: string;
  notableDecisions: string[];
};

export type ComparisonTile = {
  key: AgentKey;
  label: string;
  kind: "agent";
  previewImagePath: string;
  livePath: string;
  focusStoryPath: string;
  strategySummary: string;
};

export const STORYBOOK_BASE_URL = "http://localhost:6006";

export const STORY_IDS = {
  comparisonGrid: "solutionarticulation-comparisongate--comparison-grid",
  agentAFocus: "solutionarticulation-comparisongate--agent-a-focus",
  agentBFocus: "solutionarticulation-comparisongate--agent-b-focus",
  agentCFocus: "solutionarticulation-comparisongate--agent-c-focus",
  agentDFocus: "solutionarticulation-comparisongate--agent-d-focus",
  agentEFocus: "solutionarticulation-comparisongate--agent-e-focus",
} as const;

export const REFERENCE_IMAGE_PATH = "/implementations/reference/solution-articulation-final.jpg";

export const AGENT_CONFIG: Record<
  AgentKey,
  {
    label: string;
    mountRoot: string;
    focusStoryId: string;
    strategySummary: string;
    metadataPath: string;
  }
> = {
  "agent-a": {
    label: "Agent A",
    mountRoot: "/implementations/agent-a",
    focusStoryId: STORY_IDS.agentAFocus,
    strategySummary: "Vanilla CSS + Grid/Flex + Inline SVG + SVG path connectors + stage-based components",
    metadataPath: "/implementations/agent-a/metadata.json",
  },
  "agent-b": {
    label: "Agent B",
    mountRoot: "/implementations/agent-b",
    focusStoryId: STORY_IDS.agentBFocus,
    strategySummary: "Tailwind + Flexbox-first + icon library/raster logos + pseudo-element connectors + monolithic section",
    metadataPath: "/implementations/agent-b/metadata.json",
  },
  "agent-c": {
    label: "Agent C",
    mountRoot: "/implementations/agent-c",
    focusStoryId: STORY_IDS.agentCFocus,
    strategySummary: "CSS Modules + hybrid Grid/Flex + SVG sprite + absolute HTML/CSS connectors + data-driven render",
    metadataPath: "/implementations/agent-c/metadata.json",
  },
  "agent-d": {
    label: "Agent D",
    mountRoot: "/implementations/agent-d",
    focusStoryId: STORY_IDS.agentDFocus,
    strategySummary: "styled-components + Grid/subgrid + CSS-drawn shapes + Canvas connector overlay + atomic components",
    metadataPath: "/implementations/agent-d/metadata.json",
  },
  "agent-e": {
    label: "Agent E",
    mountRoot: "/implementations/agent-e",
    focusStoryId: STORY_IDS.agentEFocus,
    strategySummary: "CSS-in-JS + position-anchored layout + raster assets + border-based connectors + semantic HTML-first",
    metadataPath: "/implementations/agent-e/metadata.json",
  },
};

export const comparisonTiles: ComparisonTile[] = [
  ...((Object.keys(AGENT_CONFIG) as AgentKey[]).map((key) => {
    const agent = AGENT_CONFIG[key];
    return {
      key,
      label: agent.label,
      kind: "agent",
      previewImagePath: `${agent.mountRoot}/screenshots/desktop-1440.png`,
      livePath: `${agent.mountRoot}/index.html`,
      focusStoryPath: `/?path=/story/${agent.focusStoryId}`,
      strategySummary: agent.strategySummary,
    };
  })),
];

export function storyLink(storyId: string): string {
  return `${STORYBOOK_BASE_URL}/?path=/story/${storyId}`;
}

export const LINKS = {
  comparisonGrid: storyLink(STORY_IDS.comparisonGrid),
  agentAFocus: storyLink(STORY_IDS.agentAFocus),
  agentBFocus: storyLink(STORY_IDS.agentBFocus),
  agentCFocus: storyLink(STORY_IDS.agentCFocus),
  agentDFocus: storyLink(STORY_IDS.agentDFocus),
  agentEFocus: storyLink(STORY_IDS.agentEFocus),
} as const;

export const frameStyles = {
  stage: {
    width: "100%",
    aspectRatio: "16 / 9",
    borderRadius: "10px",
    border: "1px solid #D1D5DB",
    overflow: "hidden",
    backgroundColor: "#F9FAFB",
    position: "relative",
  } as CSSProperties,
  media: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    objectPosition: "top center",
    display: "block",
    border: "0",
  } as CSSProperties,
  iframe: {
    width: "100%",
    height: "100%",
    border: "0",
    display: "block",
    background: "#FFFFFF",
  } as CSSProperties,
};
