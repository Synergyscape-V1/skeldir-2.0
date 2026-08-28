import { InterfaceLocationLabel } from '../InterfaceLocationLabel/InterfaceLocationLabel';
import { ChatToggle } from '../ChatToggle/ChatToggle';
import { SidebarToggle } from '../SidebarToggle/SidebarToggle';
import styles from './TopHeader.module.css';

export interface TopHeaderProps {
  interfaceName: string;
  sidebarCollapsed: boolean;
  onSidebarToggle: () => void;
  chatOpen: boolean;
  onChatToggle: () => void;
}

export function TopHeader({
  interfaceName,
  sidebarCollapsed,
  onSidebarToggle,
  chatOpen,
  onChatToggle,
}: TopHeaderProps) {
  return (
    <div className={styles.header} data-shell-header>
      <div className={styles.leading}>
        <SidebarToggle collapsed={sidebarCollapsed} onToggle={onSidebarToggle} />
        <InterfaceLocationLabel interfaceName={interfaceName} />
      </div>
      <div className={styles.trailing}>
        {!chatOpen ? <ChatToggle open={chatOpen} onToggle={onChatToggle} /> : null}
      </div>
    </div>
  );
}
