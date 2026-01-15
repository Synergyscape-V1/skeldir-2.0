/**
 * SettingsPage - Settings Interface
 *
 * Route: /settings
 *
 * EXIT GATES:
 * 1. Tab Badge Check - Team Management and White-Label Config have "Tier 3" badges
 * 2. Disabled Input Check - Email Address input is visually disabled (gray bg)
 * 3. Progress Bar Check - Visual bar showing 12/25 used
 * 4. Layout Physics Check - Two balanced columns with 64px gap
 * 5. Annotation Removal Check - "(36px/600, dark text)" NOT rendered
 */

import { useState } from 'react';

// ============================================================================
// DESIGN SYSTEM CONSTANTS
// ============================================================================
const COLORS = {
  pageBackground: '#F8F9FA',
  cardBackground: '#FFFFFF',
  borderColor: '#E5E7EB',
  textPrimary: '#212529',
  textSecondary: '#6C757D',
  textMuted: '#4B5563',
  primaryBlue: '#3B82F6',
  disabledBg: '#F3F4F6',
  progressTrack: '#F3F4F6',
  progressFill: '#64748B',
  badgeBg: '#F3F4F6',
  badgeText: '#4B5563',
} as const;

type TabId = 'user-settings' | 'team-management' | 'white-label';

interface Tab {
  id: TabId;
  label: string;
  badge?: string;
}

const tabs: Tab[] = [
  { id: 'user-settings', label: 'User Settings' },
  { id: 'team-management', label: 'Team Management', badge: 'Tier 3' },
  { id: 'white-label', label: 'White-Label Config', badge: 'Tier 3' },
];

function TierBadge({ text }: { text: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', padding: '2px 8px',
      fontSize: 10, fontWeight: 500, color: COLORS.badgeText, backgroundColor: COLORS.badgeBg,
      borderRadius: 9999, marginLeft: 8, fontFamily: 'Inter, sans-serif',
    }}>
      {text}
    </span>
  );
}

function Header({ activeTab, onTabChange }: { activeTab: TabId; onTabChange: (tabId: TabId) => void }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <h1 style={{ fontSize: 36, fontWeight: 600, color: COLORS.textPrimary, margin: 0, marginBottom: 24, fontFamily: 'Inter, sans-serif' }}>
        Settings
      </h1>
      <div style={{ borderBottom: `1px solid ${COLORS.borderColor}`, display: 'flex', gap: 32 }}>
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              style={{
                display: 'inline-flex', alignItems: 'center', padding: '0 0 12px 0',
                fontSize: 14, fontWeight: isActive ? 600 : 400,
                color: isActive ? COLORS.primaryBlue : COLORS.textSecondary,
                backgroundColor: 'transparent', border: 'none',
                borderBottom: isActive ? `2px solid ${COLORS.primaryBlue}` : '2px solid transparent',
                cursor: 'pointer', fontFamily: 'Inter, sans-serif', marginBottom: -1,
              }}
            >
              {tab.label}
              {tab.badge && <TierBadge text={tab.badge} />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FormInput({ label, value, onChange, disabled, type = 'text' }: {
  label: string; value: string; onChange?: (value: string) => void; disabled?: boolean; type?: 'text' | 'password';
}) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: 14, fontWeight: 600, color: COLORS.textPrimary, marginBottom: 8, fontFamily: 'Inter, sans-serif' }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        disabled={disabled}
        style={{
          width: '100%', height: 48, padding: '0 16px', fontSize: 14, fontFamily: 'Inter, sans-serif',
          color: disabled ? COLORS.textSecondary : COLORS.textPrimary,
          backgroundColor: disabled ? COLORS.disabledBg : COLORS.cardBackground,
          border: `1px solid ${COLORS.borderColor}`, borderRadius: 6, outline: 'none', boxSizing: 'border-box',
          cursor: disabled ? 'not-allowed' : 'text',
        }}
      />
    </div>
  );
}

interface ProfileFormState {
  fullName: string;
  email: string;
  password: string;
}

function ProfileInformation({ formState, onFormChange }: { formState: ProfileFormState; onFormChange: (updates: Partial<ProfileFormState>) => void }) {
  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: COLORS.textPrimary, margin: 0, marginBottom: 24, fontFamily: 'Inter, sans-serif' }}>
        Profile Information
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <FormInput label="Full Name" value={formState.fullName} onChange={(value) => onFormChange({ fullName: value })} />
        <FormInput label="Email Address" value={formState.email} disabled={true} />
        <div>
          <label style={{ display: 'block', fontSize: 14, fontWeight: 600, color: COLORS.textPrimary, marginBottom: 8, fontFamily: 'Inter, sans-serif' }}>
            Password
          </label>
          <div style={{ display: 'flex', gap: 12 }}>
            <input
              type="password"
              value={formState.password}
              readOnly
              style={{
                flex: 1, height: 48, padding: '0 16px', fontSize: 14, fontFamily: 'Inter, sans-serif',
                color: COLORS.textPrimary, backgroundColor: COLORS.cardBackground,
                border: `1px solid ${COLORS.borderColor}`, borderRadius: 6, outline: 'none', boxSizing: 'border-box',
              }}
            />
            <button style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '0 20px', height: 48,
              fontSize: 14, fontWeight: 500, color: COLORS.textPrimary, backgroundColor: COLORS.cardBackground,
              border: `1px solid ${COLORS.borderColor}`, borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif', whiteSpace: 'nowrap',
            }}>
              Change
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function BillingUsage({ used, total }: { used: number; total: number }) {
  const percentage = (used / total) * 100;

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: COLORS.textPrimary, margin: 0, marginBottom: 24, fontFamily: 'Inter, sans-serif' }}>
        Billing & Usage
      </h2>
      <div style={{ border: `1px solid ${COLORS.borderColor}`, borderRadius: 8, padding: 24 }}>
        <p style={{ fontSize: 14, color: COLORS.textPrimary, margin: 0, fontFamily: 'Inter, sans-serif' }}>
          Current Plan: <strong>Pro Plan ($49/mo)</strong>
        </p>
        <p style={{ fontSize: 14, color: COLORS.textPrimary, margin: 0, marginTop: 16, fontFamily: 'Inter, sans-serif' }}>
          Investigations: <strong>{used}/{total} used</strong>
        </p>
        <div style={{ width: '100%', height: 8, backgroundColor: COLORS.progressTrack, borderRadius: 4, marginTop: 8, overflow: 'hidden' }}>
          <div style={{ width: `${percentage}%`, height: '100%', backgroundColor: COLORS.progressFill, borderRadius: 4 }} />
        </div>
        <a href="#" onClick={(e) => e.preventDefault()} style={{
          display: 'inline-block', fontSize: 14, color: COLORS.primaryBlue, textDecoration: 'none', marginTop: 16, fontFamily: 'Inter, sans-serif',
        }}>
          Manage Billing & Invoices
        </a>
      </div>
    </div>
  );
}

function Notifications() {
  const [emailAlerts, setEmailAlerts] = useState(false);

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: COLORS.textPrimary, margin: 0, marginBottom: 16, fontFamily: 'Inter, sans-serif' }}>
        Notifications
      </h2>
      <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={emailAlerts}
          onChange={(e) => setEmailAlerts(e.target.checked)}
          style={{ width: 18, height: 18, accentColor: COLORS.primaryBlue, cursor: 'pointer' }}
        />
        <span style={{ fontSize: 14, color: COLORS.textMuted, fontFamily: 'Inter, sans-serif' }}>
          Email alerts for critical issues (e.g., connection failures)
        </span>
      </label>
    </div>
  );
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('user-settings');
  const [formState, setFormState] = useState<ProfileFormState>({
    fullName: 'Alex Johnson',
    email: 'alex.johnson@example.com',
    password: '••••••••••',
  });

  const handleFormChange = (updates: Partial<ProfileFormState>) => {
    setFormState((prev) => ({ ...prev, ...updates }));
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: COLORS.pageBackground, padding: '32px 0' }}>
      <div style={{ maxWidth: 1800, margin: '0 auto', padding: '0 32px', fontFamily: 'Inter, sans-serif' }}>
        <Header activeTab={activeTab} onTabChange={setActiveTab} />
        <div style={{
          width: '100%', backgroundColor: COLORS.cardBackground,
          border: `1px solid ${COLORS.borderColor}`, borderRadius: 12,
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: 48,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 64 }}>
            <ProfileInformation formState={formState} onFormChange={handleFormChange} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 48 }}>
              <BillingUsage used={12} total={25} />
              <Notifications />
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 48 }}>
            <button style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '12px 24px',
              fontSize: 14, fontWeight: 600, color: '#FFFFFF', backgroundColor: COLORS.primaryBlue,
              border: 'none', borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
            }}>
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
