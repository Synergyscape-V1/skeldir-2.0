export interface AgentTheme {
  id: "A" | "B" | "C" | "D" | "E";
  title: string;
  navLabel: string;
  signature: string;
  fontHeading: string;
  fontBody: string;
  bg: string;
  panel: string;
  panelAlt: string;
  border: string;
  text: string;
  textMuted: string;
  accent: string;
  gradient: string;
}

export const AGENTS: AgentTheme[] = [
  {
    id: "A",
    title: "Northstar Grid",
    navLabel: "Agent A - Northstar Grid",
    signature: "Oversized cross-card numerals",
    fontHeading: "'Syne', 'Segoe UI', sans-serif",
    fontBody: "'IBM Plex Sans', 'Segoe UI', sans-serif",
    bg: "#f6f8fb",
    panel: "#ffffff",
    panelAlt: "#f2f5f9",
    border: "#d7dee7",
    text: "#17212b",
    textMuted: "#5f6f80",
    accent: "#1d6fd7",
    gradient: "linear-gradient(135deg, rgba(29,111,215,0.08), rgba(20,32,56,0.03))",
  },
  {
    id: "B",
    title: "Signal Console",
    navLabel: "Agent B - Signal Console",
    signature: "Inline sparkline rails",
    fontHeading: "'Space Grotesk', 'Segoe UI', sans-serif",
    fontBody: "'IBM Plex Sans', 'Segoe UI', sans-serif",
    bg: "#f5f7fa",
    panel: "#ffffff",
    panelAlt: "#eef3f7",
    border: "#cfd9e3",
    text: "#0f1b2a",
    textMuted: "#5d6b7a",
    accent: "#0e7c66",
    gradient: "linear-gradient(170deg, rgba(14,124,102,0.08), rgba(15,27,42,0.02))",
  },
  {
    id: "C",
    title: "Ledger Editorial",
    navLabel: "Agent C - Ledger Editorial",
    signature: "Editorial section rule rhythm",
    fontHeading: "'Playfair Display', Georgia, serif",
    fontBody: "'Source Sans 3', 'Segoe UI', sans-serif",
    bg: "#fbfaf7",
    panel: "#ffffff",
    panelAlt: "#f5f1eb",
    border: "#dfd7cc",
    text: "#231b15",
    textMuted: "#6d6056",
    accent: "#8e5f2e",
    gradient: "linear-gradient(160deg, rgba(142,95,46,0.12), rgba(255,255,255,0.35))",
  },
  {
    id: "D",
    title: "Modular Atlas",
    navLabel: "Agent D - Modular Atlas",
    signature: "Docking seam lattice cards",
    fontHeading: "'Manrope', 'Segoe UI', sans-serif",
    fontBody: "'Inter', 'Segoe UI', sans-serif",
    bg: "#f3f5f8",
    panel: "#ffffff",
    panelAlt: "#edf1f6",
    border: "#d4dce8",
    text: "#142033",
    textMuted: "#5c6b80",
    accent: "#3a67dd",
    gradient: "linear-gradient(140deg, rgba(58,103,221,0.1), rgba(24,33,45,0.03))",
  },
  {
    id: "E",
    title: "Atmos Field",
    navLabel: "Agent E - Atmos Field",
    signature: "Confidence-reactive ambient halo",
    fontHeading: "'Sora', 'Segoe UI', sans-serif",
    fontBody: "'DM Sans', 'Segoe UI', sans-serif",
    bg: "#f7fbff",
    panel: "#ffffffd9",
    panelAlt: "#f1f7ff",
    border: "#d0def1",
    text: "#122236",
    textMuted: "#546b87",
    accent: "#2b7fff",
    gradient: "radial-gradient(circle at 20% 20%, rgba(43,127,255,0.2), rgba(255,255,255,0.28) 45%, rgba(15,33,54,0.03))",
  },
];
