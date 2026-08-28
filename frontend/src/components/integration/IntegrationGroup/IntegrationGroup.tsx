import type { ReactNode } from 'react';
import { Typography } from '../../layout/Typography/Typography';
import styles from './IntegrationGroup.module.css';

export interface IntegrationGroupProps {
  title: string;
  description: string;
  children: ReactNode;
  id?: string;
}

export function IntegrationGroup({ title, description, children, id }: IntegrationGroupProps) {
  return (
    <section className={styles.group} aria-labelledby={id} data-integration-group={title}>
      <div className={styles.header}>
        <Typography variant="h2" id={id}>
          {title}
        </Typography>
        <p>{description}</p>
      </div>
      <div className={styles.cards}>{children}</div>
    </section>
  );
}
