import { describe, expect, it } from 'vitest';
import {
  channelTrendBarHeightPct,
  channelTrendDeltaVsPrior,
  channelTrendPeriodLabel,
  channelTrendYTicks,
} from '../channels/channelVerifiedTrend';

describe('channelVerifiedTrend geometry', () => {
  it('uses honest height percent with no artificial floor', () => {
    expect(channelTrendBarHeightPct(100n, 1000n)).toBe(10);
    expect(channelTrendBarHeightPct(50n, 1000n)).toBe(5);
    expect(channelTrendBarHeightPct(0n, 1000n)).toBe(0);
    expect(channelTrendBarHeightPct(1000n, 1000n)).toBe(100);
  });

  it('maps W-codes to Wk labels', () => {
    expect(channelTrendPeriodLabel('W1')).toBe('Wk 1');
    expect(channelTrendPeriodLabel('W4')).toBe('Wk 4');
  });

  it('computes WoW delta from integer minor units', () => {
    const up = channelTrendDeltaVsPrior(11000n, 10000n);
    expect(up.changeBps).toBe(1000);
    expect(up.tone).toBe('success');
    expect(up.label).toContain('+');

    const flat = channelTrendDeltaVsPrior(10000n, 10000n);
    expect(flat.tone).toBe('neutral');
    expect(flat.changeBps).toBe(0);

    const down = channelTrendDeltaVsPrior(9000n, 10000n);
    expect(down.tone).toBe('error');
    expect(down.changeBps).toBe(-1000);
  });

  it('builds Y ticks at 0, mid, and max without nice-rounding', () => {
    const ticks = channelTrendYTicks(8040000n);
    expect(ticks.map((t) => t.key)).toEqual(['max', 'mid', 'zero']);
    expect(ticks.map((t) => t.valueMinor)).toEqual([8040000n, 4020000n, 0n]);
  });
});
