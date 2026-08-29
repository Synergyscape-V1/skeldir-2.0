import { SHELL_COPY } from '../../../shell/copy';
import styles from './ChatPanelResizeHandle.module.css';

export interface ChatPanelResizeHandleProps {
  onPointerDown: (event: React.PointerEvent<HTMLButtonElement>) => void;
  onResetWidth: () => void;
}

export function ChatPanelResizeHandle({ onPointerDown, onResetWidth }: ChatPanelResizeHandleProps) {
  return (
    <button
      type="button"
      className={styles.handle}
      aria-label={SHELL_COPY.chatPanelResize}
      data-chat-panel-resize-handle
      onPointerDown={onPointerDown}
      onDoubleClick={onResetWidth}
    />
  );
}
