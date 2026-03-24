import React, { useState } from 'react';
import { Download, ChevronDown } from 'lucide-react';

/** Platform logo assets aligned with PlatformIcon (command-center) and ChannelIcon (channel-comparison). */
const PLATFORM_ICONS: Record<string, { src: string; alt: string }> = {
  google_ads: { src: '/assets/platform-icons/google-ads.svg', alt: 'Google Ads' },
  meta: { src: '/assets/platform-icons/meta-ads.svg', alt: 'Meta Ads' },
  tiktok: { src: '/assets/platform-icons/tiktok-ads.svg', alt: 'TikTok Ads' },
  linkedin: { src: '/assets/platform-icons/linkedin-ads.svg', alt: 'LinkedIn Ads' },
  pinterest: { src: '/assets/platform-icons/pinterest-ads.svg', alt: 'Pinterest Ads' },
};

const TOPBAR_ICON_SIZE = 16;

export default function TopBar({ channelName, platform = 'google_ads' }: { channelName?: string; platform?: string }) {
  const [dateRange] = useState('Last 30 days');
  const [currency] = useState('USD');

  const btnStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 12px',
    fontSize: '14px',
    fontWeight: 500,
    borderRadius: '6px',
    border: '1px solid #E2E8F0',
    background: '#FFFFFF',
    cursor: 'pointer',
    color: '#0F172A',
    fontFamily: 'var(--font-sans)',
    transition: 'background 150ms ease',
  };

  const iconMeta = PLATFORM_ICONS[platform] ?? PLATFORM_ICONS.google_ads;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '56px',
        borderBottom: '1px solid #E2E8F0',
        background: '#FFFFFF',
        padding: '0 24px',
        position: 'sticky',
        top: 0,
        zIndex: 60,
        flexShrink: 0,
      }}
    >
      {/* Left: Channel name + platform logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <img
          src={iconMeta.src}
          alt={iconMeta.alt}
          width={TOPBAR_ICON_SIZE}
          height={TOPBAR_ICON_SIZE}
          style={{ display: 'block', flexShrink: 0 }}
          loading="lazy"
          decoding="async"
        />
        <h1
          style={{
            fontSize: '20px',
            fontWeight: 800,
            color: '#0F172A',
            letterSpacing: '-0.01em',
            fontFamily: 'var(--font-sans)',
            margin: 0,
          }}
        >
          {channelName || 'Google Ads'}
        </h1>
      </div>

      {/* Right: Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button style={btnStyle}>
          <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
          {dateRange}
          <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} />
        </button>
        <button style={btnStyle}>
          {currency}
          <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} />
        </button>
        <button style={{ ...btnStyle, fontWeight: 500 }}
          onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-subtle)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'var(--bg-surface)')}>
          <Download size={13} />
          Export
        </button>
      </div>
    </div>
  );
}
