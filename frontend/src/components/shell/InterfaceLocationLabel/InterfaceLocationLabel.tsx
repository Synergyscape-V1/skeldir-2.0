import { SHELL_COPY } from '../../../shell/copy';
import styles from './InterfaceLocationLabel.module.css';

export interface InterfaceLocationLabelProps {
  interfaceName: string;
}

export function InterfaceLocationLabel({ interfaceName }: InterfaceLocationLabelProps) {
  const isWelcome = interfaceName.startsWith('Welcome Back ');
  return (
    <span
      className={styles.label}
      role="status"
      data-interface-location
      data-interface-welcome={isWelcome ? 'true' : undefined}
      aria-label={isWelcome ? interfaceName : SHELL_COPY.interfaceLocationLabel(interfaceName)}
    >
      {interfaceName}
    </span>
  );
}
