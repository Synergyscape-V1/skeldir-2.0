export type EvidenceClaimRow = {
  claim: string;
  evidence: string;
};

export type EvidenceCapabilityRow = {
  label: string;
  state: string;
};

export type EvidencePageDefinition = {
  routePath: string;
  h1: string;
  metaDescription: string;
  lastReviewed: string;
  dateModified: string;
  owner: string;
  reviewCadence: string;
  disclosureStatus:
    | "technical_disclosure_only"
    | "operator_approved"
    | "legal_review_required"
    | "blocked_missing_content";
  bluf: string;
  keyFacts: string[];
  claimRows: EvidenceClaimRow[];
  howSkeldirTreats: string;
  methodology: string;
  whatDoesNotProve: string;
  limitations: string;
  relatedProof: { href: string; label: string }[];
  relatedQuestions: { href: string; label: string }[];
  capabilityRows: EvidenceCapabilityRow[];
};
