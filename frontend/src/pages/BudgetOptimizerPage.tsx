/**
 * BudgetOptimizerPage - Budget Optimizer Interface
 *
 * Implementation based on Skeldir Frontend Design Implementation Spec.
 * Route: /budget
 *
 * EXIT GATES:
 * 1. Focused Layout Gate - Form in centered card ~800px max width
 * 2. "Recommended" Badge Gate - Badge inline next to Maximize Revenue
 * 3. Content Fidelity Gate - Exact text matches
 * 4. Component State Gate - First radio selected, checkboxes unchecked
 */

import { useState } from 'react';
import { useLocation } from 'wouter';
import { Calendar, Info, ChevronDown } from 'lucide-react';

// ============================================================================
// DESIGN SYSTEM CONSTANTS (Per spec)
// ============================================================================
const COLORS = {
  pageBackground: '#F8F9FA',
  cardBackground: '#FFFFFF',
  borderColor: '#E5E7EB',
  textPrimary: '#212529',
  textSecondary: '#6C757D',
  primaryBlue: '#3B82F6',
  recommendedBadgeBg: '#D1FAE5',
  recommendedBadgeText: '#10B981',
  infoBoxBg: '#F8F9FA',
  checkboxBorder: '#D1D5DB',
} as const;

// ============================================================================
// TYPES
// ============================================================================
type OptimizationGoal = 'maximize_revenue' | 'maximize_roas' | 'minimize_cac';

interface FormState {
  dateRange: string;
  model: string;
  goal: OptimizationGoal;
  constraints: {
    keepTotalSpend: boolean;
    maxReduction: boolean;
    minimumSpend: boolean;
  };
}

// ============================================================================
// PAGE HEADER COMPONENT
// ============================================================================
function PageHeader() {
  const [, navigate] = useLocation();

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 32,
        maxWidth: 1800,
        margin: '0 auto',
        padding: '0 32px 32px 32px',
      }}
    >
      <h1
        style={{
          fontSize: 30,
          fontWeight: 700,
          color: COLORS.textPrimary,
          margin: 0,
          fontFamily: 'Inter, sans-serif',
        }}
      >
        Budget Optimizer
      </h1>
      <button
        onClick={() => navigate('/budget/scenarios')}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 16px',
          fontSize: 14,
          fontWeight: 500,
          color: COLORS.textPrimary,
          backgroundColor: 'transparent',
          border: `1px solid ${COLORS.borderColor}`,
          borderRadius: 6,
          cursor: 'pointer',
          fontFamily: 'Inter, sans-serif',
          transition: 'all 150ms ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = COLORS.pageBackground;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
      >
        View Past Scenarios
      </button>
    </div>
  );
}

// ============================================================================
// FORM FIELD WRAPPER
// ============================================================================
interface FormFieldProps {
  label: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

function FormField({ label, children, style }: FormFieldProps) {
  return (
    <div style={{ marginTop: 24, ...style }}>
      <label
        style={{
          display: 'block',
          fontSize: 14,
          fontWeight: 600,
          color: COLORS.textPrimary,
          marginBottom: 8,
          fontFamily: 'Inter, sans-serif',
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

// ============================================================================
// DATE RANGE INPUT
// ============================================================================
function DateRangeInput({ value }: { value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        height: 48,
        padding: '0 16px',
        backgroundColor: '#FFFFFF',
        border: `1px solid ${COLORS.borderColor}`,
        borderRadius: 6,
        cursor: 'pointer',
      }}
    >
      <Calendar size={16} color={COLORS.textSecondary} />
      <span style={{ fontSize: 14, color: COLORS.textPrimary, fontFamily: 'Inter, sans-serif' }}>
        {value}
      </span>
    </div>
  );
}

// ============================================================================
// MODEL SELECT
// ============================================================================
function ModelSelect({ value }: { value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 48,
        padding: '0 16px',
        backgroundColor: '#FFFFFF',
        border: `1px solid ${COLORS.borderColor}`,
        borderRadius: 6,
        cursor: 'pointer',
      }}
    >
      <span style={{ fontSize: 14, color: COLORS.textPrimary, fontFamily: 'Inter, sans-serif' }}>
        {value}
      </span>
      <ChevronDown size={16} color={COLORS.textSecondary} />
    </div>
  );
}

// ============================================================================
// RECOMMENDED BADGE
// ============================================================================
function RecommendedBadge() {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        fontSize: 12,
        fontWeight: 600,
        color: COLORS.recommendedBadgeText,
        backgroundColor: COLORS.recommendedBadgeBg,
        borderRadius: 9999,
        marginLeft: 8,
        fontFamily: 'Inter, sans-serif',
        textTransform: 'uppercase',
        letterSpacing: '0.02em',
      }}
    >
      Recommended
    </span>
  );
}

// ============================================================================
// RADIO OPTION
// ============================================================================
interface RadioOptionProps {
  label: string;
  checked: boolean;
  onChange: () => void;
  showBadge?: boolean;
}

function RadioOption({ label, checked, onChange, showBadge }: RadioOptionProps) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', padding: '4px 0' }}>
      <div
        style={{
          width: 20,
          height: 20,
          borderRadius: '50%',
          border: `2px solid ${checked ? COLORS.primaryBlue : COLORS.checkboxBorder}`,
          backgroundColor: '#FFFFFF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginRight: 12,
          transition: 'all 150ms ease',
        }}
      >
        {checked && (
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: COLORS.primaryBlue,
            }}
          />
        )}
      </div>
      <span style={{ fontSize: 14, color: COLORS.textPrimary, fontFamily: 'Inter, sans-serif' }}>
        {label}
      </span>
      {showBadge && <RecommendedBadge />}
      <input
        type="radio"
        checked={checked}
        onChange={onChange}
        style={{ position: 'absolute', opacity: 0, pointerEvents: 'none' }}
      />
    </label>
  );
}

// ============================================================================
// CHECKBOX OPTION
// ============================================================================
interface CheckboxOptionProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function CheckboxOption({ label, checked, onChange }: CheckboxOptionProps) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', padding: '4px 0' }}>
      <div
        style={{
          width: 18,
          height: 18,
          borderRadius: 4,
          border: `1px solid ${COLORS.checkboxBorder}`,
          backgroundColor: checked ? COLORS.primaryBlue : '#FFFFFF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginRight: 12,
          transition: 'all 150ms ease',
        }}
      >
        {checked && (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2.5 6L5 8.5L9.5 3.5" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>
      <span style={{ fontSize: 14, color: COLORS.textPrimary, fontFamily: 'Inter, sans-serif' }}>
        {label}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ position: 'absolute', opacity: 0, pointerEvents: 'none' }}
      />
    </label>
  );
}

// ============================================================================
// INFO BOX
// ============================================================================
function InfoBox() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginTop: 16,
        padding: '12px 16px',
        backgroundColor: COLORS.infoBoxBg,
        borderRadius: 6,
      }}
    >
      <Info size={16} color={COLORS.textSecondary} />
      <span style={{ fontSize: 14, color: COLORS.textSecondary, fontFamily: 'Inter, sans-serif' }}>
        This takes 45-60 seconds. You'll be notified when ready.
      </span>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export default function BudgetOptimizerPage() {
  const [, navigate] = useLocation();

  const [formState, setFormState] = useState<FormState>({
    dateRange: 'Last 30 Days',
    model: 'Bayesian MMM (recommended)',
    goal: 'maximize_revenue',
    constraints: {
      keepTotalSpend: false,
      maxReduction: false,
      minimumSpend: false,
    },
  });

  const handleGoalChange = (goal: OptimizationGoal) => {
    setFormState((prev) => ({ ...prev, goal }));
  };

  const handleConstraintChange = (key: keyof FormState['constraints'], value: boolean) => {
    setFormState((prev) => ({
      ...prev,
      constraints: { ...prev.constraints, [key]: value },
    }));
  };

  const handleGenerateRecommendation = () => {
    navigate('/budget/scenarios/2471');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: COLORS.pageBackground,
        padding: '32px 0',
      }}
    >
      <div style={{ maxWidth: 1800, margin: '0 auto', padding: '0 32px', fontFamily: 'Inter, sans-serif' }}>
        <PageHeader />

        {/* Focused Form Card - centered, max-width 800px */}
        <div
          style={{
            maxWidth: 800,
            width: '100%',
            margin: '0 auto',
            backgroundColor: COLORS.cardBackground,
            border: `1px solid ${COLORS.borderColor}`,
            borderRadius: 12,
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
            padding: 40,
          }}
        >
          <FormField label="Date Range" style={{ marginTop: 0 }}>
            <DateRangeInput value={formState.dateRange} />
          </FormField>

          <FormField label="Model">
            <ModelSelect value={formState.model} />
          </FormField>

          <FormField label="Optimization Goal">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <RadioOption
                label="Maximize Revenue (recommended)"
                checked={formState.goal === 'maximize_revenue'}
                onChange={() => handleGoalChange('maximize_revenue')}
                showBadge={true}
              />
              <RadioOption
                label="Maximize ROAS"
                checked={formState.goal === 'maximize_roas'}
                onChange={() => handleGoalChange('maximize_roas')}
              />
              <RadioOption
                label="Minimize CAC"
                checked={formState.goal === 'minimize_cac'}
                onChange={() => handleGoalChange('minimize_cac')}
              />
            </div>
          </FormField>

          <FormField label="Constraints">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <CheckboxOption
                label="Keep total spend within 10%."
                checked={formState.constraints.keepTotalSpend}
                onChange={(checked) => handleConstraintChange('keepTotalSpend', checked)}
              />
              <CheckboxOption
                label="Never reduce any channel by more than 20%."
                checked={formState.constraints.maxReduction}
                onChange={(checked) => handleConstraintChange('maxReduction', checked)}
              />
              <CheckboxOption
                label="Maintain minimum $500/channel (prevent shutdown)."
                checked={formState.constraints.minimumSpend}
                onChange={(checked) => handleConstraintChange('minimumSpend', checked)}
              />
            </div>
          </FormField>

          <button
            onClick={handleGenerateRecommendation}
            style={{
              display: 'block',
              width: '100%',
              height: 48,
              marginTop: 32,
              padding: '0 24px',
              fontSize: 16,
              fontWeight: 600,
              color: '#FFFFFF',
              backgroundColor: COLORS.primaryBlue,
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              fontFamily: 'Inter, sans-serif',
              transition: 'all 150ms ease',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#2563EB'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = COLORS.primaryBlue; }}
          >
            Generate Recommendation
          </button>

          <InfoBox />
        </div>
      </div>
    </div>
  );
}
