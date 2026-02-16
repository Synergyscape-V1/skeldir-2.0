/**
 * D3.7 §6.1 — Canonical TanStack + shadcn Data Table Story
 *
 * Demonstrates: sorting, global filter, pagination with 10-row dataset.
 * This story is the "zero-interpretation" anchor for D5.3 (Channel Comparison)
 * and all table-heavy screens.
 *
 * Cursor workflow:
 *   Validate: `npm run storybook` → open "Tables / CanonicalDataTable"
 *   Check: sorting toggles, filter narrows rows, pagination navigates
 */

import type { Meta, StoryObj } from '@storybook/react-vite'
import { type ColumnDef } from '@tanstack/react-table'
import { CanonicalDataTable } from '@/components/tables/CanonicalDataTable'

/* ------------------------------------------------------------------ */
/*  Example dataset: 10 rows × 4 columns                              */
/* ------------------------------------------------------------------ */

interface ChannelRow {
  channel: string
  revenue: number
  transactions: number
  matchRate: number
}

const sampleData: ChannelRow[] = [
  { channel: 'Stripe',    revenue: 142_350.00, transactions: 1_240, matchRate: 98.2 },
  { channel: 'PayPal',    revenue:  87_210.50, transactions:   830, matchRate: 94.5 },
  { channel: 'Square',    revenue:  65_890.75, transactions:   620, matchRate: 91.8 },
  { channel: 'Adyen',     revenue: 203_450.25, transactions: 1_850, matchRate: 99.1 },
  { channel: 'Braintree', revenue:  34_567.00, transactions:   310, matchRate: 88.3 },
  { channel: 'Shopify',   revenue: 178_900.00, transactions: 1_560, matchRate: 97.4 },
  { channel: 'Klarna',    revenue:  23_456.80, transactions:   210, matchRate: 85.6 },
  { channel: 'Affirm',    revenue:  12_345.60, transactions:   105, matchRate: 82.1 },
  { channel: 'Worldpay',  revenue:  98_765.40, transactions:   890, matchRate: 96.0 },
  { channel: 'Checkout',  revenue:  56_789.30, transactions:   480, matchRate: 93.2 },
]

const columns: ColumnDef<ChannelRow, unknown>[] = [
  {
    accessorKey: 'channel',
    header: 'Channel',
  },
  {
    accessorKey: 'revenue',
    header: 'Revenue',
    cell: ({ getValue }) =>
      `$${(getValue() as number).toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
  },
  {
    accessorKey: 'transactions',
    header: 'Transactions',
    cell: ({ getValue }) => (getValue() as number).toLocaleString('en-US'),
  },
  {
    accessorKey: 'matchRate',
    header: 'Match Rate',
    cell: ({ getValue }) => `${getValue()}%`,
  },
]

/* ------------------------------------------------------------------ */
/*  Stories                                                            */
/* ------------------------------------------------------------------ */

const meta: Meta = {
  title: 'Tables/CanonicalDataTable',
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'Reference TanStack Table + shadcn UI integration. ' +
          'Sorting, filtering, and pagination are interactive.',
      },
    },
  },
  tags: ['autodocs'],
}

export default meta

type Story = StoryObj

export const Default: Story = {
  render: () => (
    <CanonicalDataTable
      columns={columns}
      data={sampleData}
      pageSize={5}
      filterPlaceholder="Search channels…"
    />
  ),
}

export const SmallPageSize: Story = {
  render: () => (
    <CanonicalDataTable
      columns={columns}
      data={sampleData}
      pageSize={3}
      filterPlaceholder="Search channels…"
    />
  ),
}

export const EmptyState: Story = {
  render: () => (
    <CanonicalDataTable
      columns={columns}
      data={[]}
      pageSize={5}
      filterPlaceholder="Search channels…"
    />
  ),
}
