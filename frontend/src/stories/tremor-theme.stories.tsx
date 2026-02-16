/**
 * D3.7 §6.3 — Tremor Theme Verification Story
 *
 * Displays Tremor components to verify theme integration with D0 tokens:
 *   - Card, Metric, AreaChart, BarChart, DonutChart, Tracker
 *   - Light/dark mode validation via Storybook toolbar toggle
 *
 * Cursor workflow:
 *   Validate: `npm run storybook` → open "Theme / Tremor Theme Verification"
 *   Check: Toggle light/dark. Charts should use D0 primary color.
 */

import type { Meta, StoryObj } from '@storybook/react-vite'
import {
  Card,
  Metric,
  Text,
  AreaChart,
  BarChart,
  DonutChart,
  Tracker,
  Flex,
  Grid,
  Title,
  Badge,
} from '@tremor/react'

/* ------------------------------------------------------------------ */
/*  Sample data                                                        */
/* ------------------------------------------------------------------ */

const areaChartData = [
  { month: 'Jan', Revenue: 42_000, Expenses: 28_000 },
  { month: 'Feb', Revenue: 48_000, Expenses: 30_500 },
  { month: 'Mar', Revenue: 51_000, Expenses: 29_000 },
  { month: 'Apr', Revenue: 46_500, Expenses: 31_200 },
  { month: 'May', Revenue: 58_000, Expenses: 33_400 },
  { month: 'Jun', Revenue: 62_000, Expenses: 35_100 },
]

/**
 * D3.7 Scientific Data Derivation — Channel Revenue Breakdown
 * 
 * Source: Canonical channel data from canonical-data-table.stories.tsx
 * Method: Verified = revenue × (matchRate / 100), Unverified = revenue - Verified
 * 
 * All 10 channels from canonical dataset included for consistency.
 */
const barChartData = [
  { channel: 'Stripe',    Verified: 139_787.70, Unverified: 2_562.30 },
  { channel: 'PayPal',    Verified: 82_414.02, Unverified: 4_796.48 },
  { channel: 'Square',    Verified: 60_487.71, Unverified: 5_403.04 },
  { channel: 'Adyen',     Verified: 201_619.20, Unverified: 1_831.05 },
  { channel: 'Braintree', Verified: 30_522.66, Unverified: 4_044.34 },
  { channel: 'Shopify',   Verified: 174_248.60, Unverified: 4_651.40 },
  { channel: 'Klarna',    Verified: 20_079.02, Unverified: 3_377.78 },
  { channel: 'Affirm',    Verified: 10_135.74, Unverified: 2_209.86 },
  { channel: 'Worldpay',  Verified: 94_814.78, Unverified: 3_950.62 },
  { channel: 'Checkout',  Verified: 52_927.63, Unverified: 3_861.67 },
]

/**
 * D3.7 Scientific Data Consistency — Derived from barChartData totals
 * Verified: 867,037 (sum of all Verified from barChartData)
 * Unverified: 36,689 (sum of all Unverified from barChartData)
 * Pending: 0 (not applicable for this dataset)
 */
const donutChartData = [
  { name: 'Verified', value: 867_037 },
  { name: 'Unverified', value: 36_689 },
  { name: 'Pending', value: 0 },
]

const trackerData = [
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'yellow' as const, tooltip: 'Degraded' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'red' as const, tooltip: 'Downtime' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'yellow' as const, tooltip: 'Degraded' },
  { color: 'emerald' as const, tooltip: 'Operational' },
  { color: 'emerald' as const, tooltip: 'Operational' },
]

/* ------------------------------------------------------------------ */
/*  Showcase Component                                                 */
/* ------------------------------------------------------------------ */

function TremorThemeShowcase() {
  return (
    <div className="space-y-8 p-6 bg-background text-foreground min-h-screen">
      <h1 className="text-2xl font-bold">Tremor Theme Verification</h1>
      <p className="text-muted-foreground">
        Tremor components below should inherit D0 token colors via the
        tremor-brand/tremor-background/tremor-content/tremor-ring mappings
        in tailwind.config. Toggle light/dark in the toolbar.
      </p>

      {/* ---- Card + Metric ---- */}
      <Grid numItems={1} numItemsSm={2} numItemsLg={3} className="gap-4">
        <Card>
          <Text>Total Revenue</Text>
          <Metric>$903,726</Metric>
          <Flex className="mt-2">
            <Badge color="emerald">+12.3%</Badge>
            <Text>vs last month</Text>
          </Flex>
        </Card>

        <Card>
          <Text>Verified Revenue</Text>
          <Metric>$867,037</Metric>
          <Flex className="mt-2">
            <Badge color="emerald">96.0%</Badge>
            <Text>match rate</Text>
          </Flex>
        </Card>

        <Card>
          <Text>Active Channels</Text>
          <Metric>10</Metric>
          <Flex className="mt-2">
            <Badge color="blue">All connected</Badge>
          </Flex>
        </Card>
      </Grid>

      {/* ---- AreaChart ---- */}
      <Card>
        <Title>Revenue vs Expenses (Area Chart)</Title>
        <AreaChart
          className="mt-4 h-72"
          data={areaChartData}
          index="month"
          categories={['Revenue', 'Expenses']}
          colors={['blue', 'rose']}
          valueFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
        />
      </Card>

      {/* ---- BarChart ---- */}
      <Card>
        <Title>Channel Revenue Breakdown (Bar Chart)</Title>
        <BarChart
          className="mt-4 h-72"
          data={barChartData}
          index="channel"
          categories={['Verified', 'Unverified']}
          colors={['emerald', 'amber']}
          valueFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
        />
      </Card>

      {/* ---- DonutChart ---- */}
      <Card>
        <Title>Revenue Distribution (Donut Chart)</Title>
        <DonutChart
          className="mt-4 h-60"
          data={donutChartData}
          index="name"
          category="value"
          colors={['emerald', 'amber', 'slate']}
          valueFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
        />
      </Card>

      {/* ---- Tracker ---- */}
      <Card>
        <Title>Ingestion Pipeline Uptime (Tracker)</Title>
        <Text>Last 14 days</Text>
        <Tracker data={trackerData} className="mt-4" />
      </Card>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Story                                                              */
/* ------------------------------------------------------------------ */

const meta: Meta = {
  title: 'Theme/Tremor Theme Verification',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Tremor component showcase: Card, Metric, AreaChart, BarChart, ' +
          'DonutChart, and Tracker. Validates D0 token integration for light/dark.',
      },
    },
  },
  tags: ['autodocs'],
}

export default meta

type Story = StoryObj

export const LightMode: Story = {
  render: () => <TremorThemeShowcase />,
}
