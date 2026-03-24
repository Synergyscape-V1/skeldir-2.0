import type { BudgetRecommendation, WinnerDeclaration } from "../../types/comparison";

interface ModelRecommendationProps {
  winner: WinnerDeclaration | null;
  recommendation: BudgetRecommendation | null;
}

export function ModelRecommendation({ winner, recommendation }: ModelRecommendationProps) {
  const winnerName = winner?.channelName ?? "the top channel";
  const loserName = recommendation?.fromChannelName ?? "the lower-performing channel";

  return (
    <div className="dc-model-recommendation">
      <div>
        <h3 className="dc-recommendation-title">Why this model recommendation</h3>
        <p className="dc-recommendation-body">
          <strong>Our model identifies {winnerName} as the most reliably profitable channel.</strong>{" "}
          Shifting budget from the higher volatility {loserName} maximizes probability of better returns.
        </p>
        <p className="dc-recommendation-disclaimer">
          Final budget allocation requires your approval.
        </p>
      </div>
      <button type="button" className="dc-btn-success">
        Open in Budget Optimizer
      </button>
    </div>
  );
}
