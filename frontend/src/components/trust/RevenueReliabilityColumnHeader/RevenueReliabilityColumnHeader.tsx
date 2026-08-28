import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { IconInfo } from '../../icons/StatusIcons';
import {
  REVENUE_RELIABILITY_COLUMN_HEADER,
  REVENUE_RELIABILITY_HEADER_TOOLTIP,
} from '../../../trust/revenueReliabilityCopy';
import shared from '../../../styles/shared.module.css';
import styles from './RevenueReliabilityColumnHeader.module.css';

const TOOLTIP_GAP_PX = 8;
const TOOLTIP_MAX_WIDTH_PX = 280;

interface TooltipCoords {
  top: number;
  left: number;
}

function clampTooltipLeft(preferredLeft: number, tooltipWidth: number): number {
  const margin = 8;
  const maxLeft = window.innerWidth - tooltipWidth - margin;
  return Math.max(margin, Math.min(preferredLeft, maxLeft));
}

export function RevenueReliabilityColumnHeader() {
  const tooltipId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<TooltipCoords | null>(null);

  const updatePosition = () => {
    const trigger = triggerRef.current;
    if (!trigger) return;

    const rect = trigger.getBoundingClientRect();
    const tooltipWidth = tooltipRef.current?.offsetWidth ?? TOOLTIP_MAX_WIDTH_PX;
    const preferredLeft = rect.right - tooltipWidth;
    setCoords({
      top: rect.bottom + TOOLTIP_GAP_PX,
      left: clampTooltipLeft(preferredLeft, tooltipWidth),
    });
  };

  useLayoutEffect(() => {
    if (!open) {
      setCoords(null);
      return;
    }
    updatePosition();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const onReposition = () => updatePosition();
    window.addEventListener('scroll', onReposition, true);
    window.addEventListener('resize', onReposition);
    return () => {
      window.removeEventListener('scroll', onReposition, true);
      window.removeEventListener('resize', onReposition);
    };
  }, [open]);

  const tooltip =
    open && typeof document !== 'undefined'
      ? createPortal(
          <span
            ref={tooltipRef}
            id={tooltipId}
            role="tooltip"
            className={styles.tooltip}
            data-revenue-reliability-header-tooltip
            style={
              coords
                ? { top: coords.top, left: coords.left, visibility: 'visible' }
                : { top: 0, left: 0, visibility: 'hidden' }
            }
          >
            {REVENUE_RELIABILITY_HEADER_TOOLTIP}
          </span>,
          document.body,
        )
      : null;

  return (
    <span className={styles.header} data-revenue-reliability-column-header>
      <span className={styles.label} data-revenue-reliability-label>
        {REVENUE_RELIABILITY_COLUMN_HEADER}
        <button
          ref={triggerRef}
          type="button"
          className={[styles.infoButton, shared.focusVisible].join(' ')}
          aria-label={`${REVENUE_RELIABILITY_COLUMN_HEADER}. ${REVENUE_RELIABILITY_HEADER_TOOLTIP}`}
          aria-describedby={open ? tooltipId : undefined}
          aria-expanded={open}
          data-revenue-reliability-header-info
          onClick={(event) => {
            // Keep sort headers from flipping when the footnote control is activated.
            event.stopPropagation();
          }}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
        >
          <IconInfo className={styles.infoIcon} title="" />
        </button>
      </span>
      {tooltip}
    </span>
  );
}
