import shieldMark from '../../../assets/icons/brand/shield-mark.svg';
import wordmarkSvg from '../../../assets/icons/brand/wordmark.svg';
import styles from './AuthBrand.module.css';

const SHIELD_SIZE = 60;
const WORDMARK_HEIGHT = 26;
const WORDMARK_WIDTH = 108;

export function AuthBrand() {
  return (
    <div className={styles.brand} data-auth-brand aria-label="Skeldir">
      <div className={styles.lockup} data-auth-brand-lockup>
        <img
          src={shieldMark}
          alt=""
          className={styles.shield}
          width={SHIELD_SIZE}
          height={SHIELD_SIZE}
          data-auth-brand-shield
        />
        <img
          src={wordmarkSvg}
          alt=""
          className={styles.wordmark}
          width={WORDMARK_WIDTH}
          height={WORDMARK_HEIGHT}
          data-auth-brand-wordmark
        />
      </div>
    </div>
  );
}
