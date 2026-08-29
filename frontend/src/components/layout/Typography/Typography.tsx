import type { ElementType, HTMLAttributes } from 'react';
import { classNames } from '../../../lib/utils';
import styles from './Typography.module.css';

export type TypographyVariant = 'h1' | 'h2' | 'h3' | 'body' | 'small' | 'code';

const variantElement: Record<TypographyVariant, ElementType> = {
  h1: 'h1',
  h2: 'h2',
  h3: 'h3',
  body: 'p',
  small: 'span',
  code: 'code',
};

export interface TypographyProps extends HTMLAttributes<HTMLElement> {
  variant: TypographyVariant;
  as?: ElementType;
}

export function Typography({ variant, as, className, children, ...rest }: TypographyProps) {
  const Component = (as ?? variantElement[variant]) as ElementType;
  return (
    <Component className={classNames(styles[variant], className)} {...rest}>
      {children}
    </Component>
  );
}
