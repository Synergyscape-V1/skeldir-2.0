import { isChannelLogoPlaceholder, resolveChannelLogoSrc } from './channelLogoMap';
import styles from './ChannelLogo.module.css';

export function ChannelLogo({ claimSource }: { claimSource: string }) {
  const src = resolveChannelLogoSrc(claimSource);
  const placeholder = isChannelLogoPlaceholder(claimSource);

  return (
    <img
      src={src}
      alt=""
      className={styles.logo}
      data-channel-logo={claimSource}
      {...(placeholder ? { 'data-channel-logo-placeholder': 'true' } : {})}
    />
  );
}
