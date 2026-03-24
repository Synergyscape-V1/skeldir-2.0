import React, { useEffect, useMemo, useState } from "react";
import type { ChannelComparisonVariantManifest } from "../../types/comparison";

interface ChannelComparisonEvaluationPanelProps {
  manifests: ChannelComparisonVariantManifest[];
}

function storageKey(agentId: string): string {
  return `channel-comparison-eval-note-${agentId}`;
}

export function ChannelComparisonEvaluationPanel({
  manifests,
}: ChannelComparisonEvaluationPanelProps) {
  const [notes, setNotes] = useState<Record<string, string>>({});

  useEffect(() => {
    const next: Record<string, string> = {};
    manifests.forEach((manifest) => {
      if (typeof window === "undefined") return;
      next[manifest.agentId] = window.localStorage.getItem(storageKey(manifest.agentId)) ?? "";
    });
    setNotes(next);
  }, [manifests]);

  const summary = useMemo(() => {
    return manifests.map((manifest) => ({
      agentId: manifest.agentId,
      passCount: manifest.validation.filter((gate) => gate.pass).length,
      total: manifest.validation.length,
    }));
  }, [manifests]);

  return (
    <aside className="cc-evaluation-panel">
      <h2>Evaluation Scaffold</h2>
      <p>Use this panel to review hypothesis intent, gate evidence, and capture final observations per iteration.</p>
      {manifests.map((manifest) => {
        const gateSummary = summary.find((item) => item.agentId === manifest.agentId);
        return (
          <section key={manifest.agentId} className="cc-eval-card">
            <header>
              <h3>
                Agent {manifest.agentId} ({gateSummary?.passCount}/{gateSummary?.total} gates)
              </h3>
            </header>
            <p>{manifest.hypothesis}</p>
            <ul>
              {manifest.validation.map((gate) => (
                <li key={gate.key}>
                  <strong>{gate.label}:</strong> {gate.pass ? "PASS" : "FAIL"} - {gate.evidence}
                </li>
              ))}
            </ul>
            <label htmlFor={`cc-note-${manifest.agentId}`}>Operator notes</label>
            <textarea
              id={`cc-note-${manifest.agentId}`}
              value={notes[manifest.agentId] ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                setNotes((prev) => ({ ...prev, [manifest.agentId]: value }));
                if (typeof window !== "undefined") {
                  window.localStorage.setItem(storageKey(manifest.agentId), value);
                }
              }}
              placeholder={`Observations for Agent ${manifest.agentId}`}
            />
          </section>
        );
      })}
    </aside>
  );
}
