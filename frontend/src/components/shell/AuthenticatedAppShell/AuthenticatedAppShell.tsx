import { Outlet, useLocation } from 'react-router-dom';
import { useCallback, useRef, useState, type CSSProperties } from 'react';
import { ResponsiveShell } from '../../layout/ResponsiveShell/ResponsiveShell';
import { ACTIVATION_COPY } from '../../../activation/copy';
import { getAuthState } from '../../../auth/sessionStore';
import { GOVERNANCE_COPY } from '../../../governance/copy';
import { BILLING_COPY } from '../../../billing/copy';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import { SHELL_COPY } from '../../../shell/copy';
import { readChatPanelDefaultWidth } from '../../../shell/chatPanelLayout';
import { parseShellNavPath, resolveHeaderLocationLabel } from '../../../shell/navigation';
import type { ShellNavItemId } from '../../../shell/types';
import shared from '../../../styles/shared.module.css';
import { ChatPanel } from '../ChatPanel/ChatPanel';
import { ChatPanelResizeHandle } from '../ChatPanelResizeHandle/ChatPanelResizeHandle';
import { useChatPanelResize } from '../ChatPanelResizeHandle/useChatPanelResize';
import { MobileBottomNavigation } from '../MobileBottomNavigation/MobileBottomNavigation';
import { NotificationBell } from '../NotificationBell/NotificationBell';
import { SidebarNavigation } from '../SidebarNavigation/SidebarNavigation';
import { TopHeader } from '../TopHeader/TopHeader';
import { RouteContainer } from '../RouteContainer/RouteContainer';
import { useChatPanelLayoutMode } from './useChatPanelLayoutMode';
import styles from './AuthenticatedAppShell.module.css';

export interface AuthenticatedAppShellProps {
  pageTitle?: string;
  moreSheetOpen?: boolean;
}

function resolvePageTitle(pathname: string, override?: string): string {
  if (override) return override;
  if (pathname.startsWith('/app/onboarding')) {
    return pathname.includes('/complete')
      ? ACTIVATION_COPY.completion.title
      : ACTIVATION_COPY.onboardingTitle;
  }
  if (pathname.startsWith('/app/integrations')) return ACTIVATION_COPY.integrationsPageTitle;
  if (pathname.startsWith('/app/settings/billing')) return BILLING_COPY.pageTitle;
  if (pathname.startsWith('/app/settings/team')) return GOVERNANCE_COPY.teamPageTitle;
  if (pathname.startsWith('/app/settings/policy')) return GOVERNANCE_COPY.policyPageTitle;
  if (pathname.startsWith('/app/audit')) return OPERATIONAL_AUDIT_COPY.auditPageTitle;
  if (pathname.startsWith('/app/diagnostics')) return OPERATIONAL_AUDIT_COPY.diagnosticsPageTitle;
  if (pathname === '/app' || pathname === '/app/') return SHELL_COPY.pageTitleDefault;
  return SHELL_COPY.pageTitleDefault;
}

function resolveActiveNavId(pathname: string): ShellNavItemId | 'landing' | 'onboarding' | 'integrations' {
  if (pathname.startsWith('/app/onboarding')) return 'onboarding';
  if (pathname.startsWith('/app/integrations')) return 'integrations';
  if (pathname.startsWith('/app/settings')) return 'settings';
  if (pathname.startsWith('/app/audit')) return 'audit-ledger';
  if (pathname.startsWith('/app/diagnostics')) return 'audit-ledger';
  if (pathname === '/app' || pathname === '/app/') return 'command-center';
  if (pathname === '/shell') return 'landing';
  return parseShellNavPath(pathname) ?? 'landing';
}

function usesInPagePageHeading(pathname: string): boolean {
  if (pathname === '/app' || pathname === '/app/') return true;
  if (pathname === '/app/claims' || pathname.startsWith('/app/claims/')) return true;
  return false;
}

export function AuthenticatedAppShell({
  pageTitle,
  moreSheetOpen,
}: AuthenticatedAppShellProps) {
  const location = useLocation();
  const appShellRef = useRef<HTMLDivElement>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatPanelWidth, setChatPanelWidth] = useState<number | null>(null);
  const activeNavId = resolveActiveNavId(location.pathname);
  const resolvedTitle = resolvePageTitle(location.pathname, pageTitle);
  const routeLandmarkTitle = usesInPagePageHeading(location.pathname) ? undefined : resolvedTitle;
  const density =
    location.pathname.startsWith('/app/onboarding') ? 'comfortable' : 'enterprise-compact';

  const resetChatPanelWidth = useCallback(() => {
    setChatPanelWidth(readChatPanelDefaultWidth(appShellRef.current));
  }, []);

  const handleChatToggle = useCallback(() => {
    setChatOpen((open) => {
      if (!open) {
        resetChatPanelWidth();
      }
      return !open;
    });
  }, [resetChatPanelWidth]);

  const chatLayoutMode = useChatPanelLayoutMode(
    chatOpen,
    sidebarCollapsed,
    chatPanelWidth,
    appShellRef.current,
  );

  const { startResize } = useChatPanelResize({
    enabled: chatOpen && chatLayoutMode === 'docked',
    onWidthChange: setChatPanelWidth,
  });

  const shellStyle = {
    ...(chatOpen && chatPanelWidth !== null
      ? { '--shell-chat-panel-current-width': `${chatPanelWidth}px` }
      : {}),
  } as CSSProperties;

  return (
    <div
      ref={appShellRef}
      className={styles.appShell}
      style={shellStyle}
      data-authenticated-app-shell
      data-density={density}
      data-route="/app"
      data-shell-sidebar-collapsed={sidebarCollapsed ? 'true' : 'false'}
      data-shell-chat-open={chatOpen ? 'true' : 'false'}
      data-shell-chat-layout={chatLayoutMode}
    >
      <a href="#shell-main-content" className={[styles.skipLink, shared.focusVisible].join(' ')}>
        {SHELL_COPY.skipToContent}
      </a>
      <ResponsiveShell
        landmarkMode="semantic"
        viewportLabel="app-shell"
        header={
          <TopHeader
            interfaceName={resolveHeaderLocationLabel(
              location.pathname,
              getAuthState().tenant?.workspaceName,
            )}
            sidebarCollapsed={sidebarCollapsed}
            onSidebarToggle={() => setSidebarCollapsed((value) => !value)}
            chatOpen={chatOpen}
            onChatToggle={handleChatToggle}
          />
        }
        trailing={
          <div className={styles.chatShell} data-shell-chat-shell>
            {chatOpen && chatLayoutMode === 'docked' ? (
              <ChatPanelResizeHandle onPointerDown={startResize} onResetWidth={resetChatPanelWidth} />
            ) : null}
            <ChatPanel open={chatOpen} onChatToggle={handleChatToggle} />
          </div>
        }
        sidebar={
          <div
            className={styles.sidebarWrap}
            data-shell-sidebar-desktop
            aria-hidden={sidebarCollapsed ? true : undefined}
          >
            <SidebarNavigation activeNavId={activeNavId} />
          </div>
        }
      >
        <RouteContainer pageTitle={routeLandmarkTitle}>
          <div id="shell-main-content" tabIndex={-1}>
            <Outlet />
          </div>
        </RouteContainer>
      </ResponsiveShell>
      {chatOpen && (chatLayoutMode === 'mobile' || chatLayoutMode === 'overlay') ? (
        <button
          type="button"
          className={styles.chatBackdrop}
          aria-label={SHELL_COPY.chatToggleClose}
          onClick={() => setChatOpen(false)}
          data-shell-chat-backdrop
        />
      ) : null}
      <div className={styles.mobileNotification} data-shell-mobile-notification>
        <NotificationBell unreadCount={3} />
      </div>
      <MobileBottomNavigation activeNavId={activeNavId} moreSheetOpen={moreSheetOpen} />
    </div>
  );
}
