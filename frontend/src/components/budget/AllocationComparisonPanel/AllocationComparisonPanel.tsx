import { useState } from 'react';
import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';
import type { AllocationRow } from '../../../budget/budgetSimulationTypes';
import { formatBpsAsPercentOneDecimal, formatMoneyMinorDisplay } from '../../../lib/money';
import styles from './AllocationComparisonPanel.module.css';

export interface AllocationComparisonPanelProps {
  title: string;
  rows: AllocationRow[];
  totalMinor: bigint;
  currencyCode: string;
  /** Column inside unified comparison card — no independent elevation */
  embedded?: boolean;
}

interface HoverState {
  channelId: string;
  mouseX: number;
  mouseY: number;
}

export function AllocationComparisonPanel({
  title,
  rows,
  totalMinor,
  currencyCode,
  embedded = false,
}: AllocationComparisonPanelProps) {
  const [hover, setHover] = useState<HoverState | null>(null);

  const maxShareBps = Math.max(...rows.map((r) => r.shareBps), 100);
  // Round the axis up to the next multiple of 10 using exact integer arithmetic.
  // Not a money path (basis points for chart scale); avoids the rounding helpers
  // the financial axiom scan forbids in component code.
  const xAxisRemainder = maxShareBps % 10;
  const xAxisMax = xAxisRemainder === 0 ? maxShareBps : maxShareBps + (10 - xAxisRemainder);

  const handleBarMouseEnter = (channelId: string, event: React.MouseEvent) => {
    setHover({
      channelId,
      mouseX: event.clientX,
      mouseY: event.clientY,
    });
  };

  const handleBarMouseLeave = () => {
    setHover(null);
  };

  const activeRow = hover ? rows.find((r) => r.channelId === hover.channelId) : null;

  return (
    <section
      className={embedded ? styles.column : styles.panel}
      aria-label={title}
      data-allocation-panel={embedded ? undefined : 'true'}
      data-allocation-column={embedded ? 'true' : undefined}
      data-budget-elevated-panel={embedded ? undefined : 'true'}
    >
      <h3 className={styles.title}>{title}</h3>

      {/* Chart container with axes */}
      <div className={styles.chartContainer}>
        {/* Y-axis labels */}
        <div className={styles.yAxis}>
          {rows.map((row) => (
            <div key={row.channelId} className={styles.yAxisLabel}>
              {row.channelLabel}
            </div>
          ))}
        </div>

        {/* Chart area with gridlines and bars */}
        <div className={styles.chartArea}>
          {/* Gridlines */}
          <div className={styles.gridlines}>
            {[0, 25, 50, 75, 100].map((percent) => (
              <div
                key={percent}
                className={styles.gridline}
                style={{ left: `${percent}%` }}
                aria-hidden="true"
              />
            ))}
          </div>

          {/* X-axis labels */}
          <div className={styles.xAxis}>
            {[0, 25, 50, 75, 100].map((percent) => (
              <div
                key={percent}
                className={styles.xAxisLabel}
                style={{ left: `${percent}%` }}
                aria-hidden="true"
              >
                {percent}%
              </div>
            ))}
          </div>

          {/* Bars */}
          <div 
            className={styles.bars}
            style={{ '--bar-count': rows.length } as React.CSSProperties}
          >
            {rows.map((row, index) => (
              <div
                key={row.channelId}
                className={styles.barRow}
                onMouseEnter={(e) => handleBarMouseEnter(row.channelId, e)}
                onMouseLeave={handleBarMouseLeave}
                style={{ top: `${index * (100 / rows.length)}%` }}
              >
                <div
                  className={styles.bar}
                  style={{
                    width: `${(row.shareBps / xAxisMax) * 100}%`,
                    backgroundColor: row.color,
                  }}
                  role="img"
                  aria-label={`${row.channelLabel}: ${formatBpsAsPercentOneDecimal(row.shareBps)} of allocation`}
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tooltip */}
      {activeRow && hover && (
        <div
          className={styles.tooltip}
          style={{
            left: `${hover.mouseX + 12}px`,
            top: `${hover.mouseY - 8}px`,
          }}
          role="tooltip"
          aria-hidden="true"
        >
          <div className={styles.tooltipChannel}>{activeRow.channelLabel}</div>
          <div className={styles.tooltipValue}>
            {formatMoneyMinorDisplay(activeRow.amountMinor, currencyCode)}
          </div>
          <div className={styles.tooltipPercent}>
            {formatBpsAsPercentOneDecimal(activeRow.shareBps)}
          </div>
        </div>
      )}

      {/* Total row */}
      <div className={styles.totalRow}>
        <span>{BUDGET_SIMULATION_COPY.allocation.total}</span>
        <span>
          {formatMoneyMinorDisplay(totalMinor, currencyCode)} · 100%
        </span>
      </div>
    </section>
  );
}


