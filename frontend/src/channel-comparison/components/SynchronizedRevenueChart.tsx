import React, { useMemo } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ComparisonChannelData } from "../../types/comparison";
import { CHANNEL_COLORS, DATE_RANGE_LABELS } from "../core/constants";
import type { DateRangeValue } from "../../types/channel";

interface SynchronizedRevenueChartProps {
  channels: ComparisonChannelData[];
  dateRange: DateRangeValue;
}

type Row = { date: string } & Record<string, number | string>;

function mergeRows(channels: ComparisonChannelData[]): Row[] {
  if (channels.length === 0) return [];
  return channels[0].trendData.map((point, index) => {
    const row: Row = {
      date: new Date(point.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    };
    channels.forEach((channel) => {
      row[channel.channel.id] = Math.round((channel.trendData[index]?.revenue ?? 0) / 100);
    });
    return row;
  });
}

export function SynchronizedRevenueChart({ channels, dateRange }: SynchronizedRevenueChartProps) {
  const rows = useMemo(() => mergeRows(channels), [channels]);

  if (channels.length < 2) return null;

  return (
    <figure
      className="cc-revenue-chart"
      role="figure"
      aria-label={`Revenue trend comparison chart for ${channels.map((channel) => channel.channel.name).join(", ")}`}
    >
      <figcaption>Revenue Trend Comparison - {DATE_RANGE_LABELS[dateRange]}</figcaption>
      <div className="cc-revenue-chart-canvas">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={rows}>
            <XAxis dataKey="date" tick={{ fontSize: 12, fill: "var(--text-secondary)" }} tickLine={false} axisLine={false} />
            <YAxis
              tick={{ fontSize: 12, fill: "var(--text-secondary)" }}
              tickLine={false}
              axisLine={false}
              width={60}
              tickFormatter={(value: number) => `$${Math.round(value / 1000)}k`}
            />
            <Tooltip
              formatter={(value: number | string | undefined, channelId: string | undefined) => {
                const numericValue = typeof value === "number" ? value : Number(value ?? 0);
                const resolvedChannelId = channelId ?? "";
                const channel = channels.find((item) => item.channel.id === resolvedChannelId);
                return [`$${numericValue.toLocaleString()}`, channel?.channel.name ?? resolvedChannelId];
              }}
            />
            {channels.map((channel, index) => (
              <Line
                key={channel.channel.id}
                dataKey={channel.channel.id}
                stroke={CHANNEL_COLORS[index] ?? CHANNEL_COLORS[0]}
                strokeWidth={2}
                dot={false}
                type="monotone"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
