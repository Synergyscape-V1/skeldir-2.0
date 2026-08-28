import { useNavigate } from 'react-router-dom';
import { buildClaimTrustDrawerHref } from '../../../trustIndex/envelopeClaimRouting';

import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';

import { Table, type TableColumn } from '../../layout/Table/Table';

import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';

import { channelColorForId } from '../../../budget/budgetFixtures';

import type { SourceTrustEnvelopeRow } from '../../../budget/budgetSimulationTypes';

import { formatMoneyMinorDisplay } from '../../../lib/money';

import shared from '../../../styles/shared.module.css';

import styles from './SourceTrustEnvelopesTable.module.css';



export interface SourceTrustEnvelopesTableProps {

  rows: SourceTrustEnvelopeRow[];

  currencyCode: string;

}



export function SourceTrustEnvelopesTable({ rows, currencyCode }: SourceTrustEnvelopesTableProps) {

  const navigate = useNavigate();



  const columns: TableColumn<SourceTrustEnvelopeRow>[] = [

    {

      key: 'envelopeId',

      header: BUDGET_SIMULATION_COPY.sourceEnvelopes.envelopeId,

      render: (row) => <code className={styles.code}>{row.envelopeId}</code>,

    },

    {

      key: 'channel',

      header: BUDGET_SIMULATION_COPY.sourceEnvelopes.channel,

      render: (row) => (

        <span className={shared.iconWithLabel}>

          <span className={styles.channelDot} style={{ background: channelColorForId(row.channelId) }} aria-hidden />

          <span>{row.channelLabel}</span>

        </span>

      ),

    },

    {

      key: 'authority',

      header: BUDGET_SIMULATION_COPY.sourceEnvelopes.authority,

      render: (row) => <AuthorityBadge authority={row.authority} size="table" />,

    },

    {

      key: 'role',

      header: BUDGET_SIMULATION_COPY.sourceEnvelopes.contributionRole,

      render: (row) =>

        row.contributionRole === 'primary'

          ? BUDGET_SIMULATION_COPY.sourceEnvelopes.primary

          : BUDGET_SIMULATION_COPY.sourceEnvelopes.supporting,

    },

    {

      key: 'revenue',

      header: BUDGET_SIMULATION_COPY.sourceEnvelopes.verifiedRevenue,

      render: (row) => formatMoneyMinorDisplay(row.verifiedRevenueMinor, currencyCode),

    },

    {

      key: 'open',

      header: BUDGET_SIMULATION_COPY.sourceEnvelopes.open,

      render: (row) => (

        <button

          type="button"

          className={[styles.openButton, shared.focusVisible].join(' ')}

          onClick={(e) => {

            e.stopPropagation();

            navigate(buildClaimTrustDrawerHref(row.envelopeId));

          }}

        >

          {BUDGET_SIMULATION_COPY.sourceEnvelopes.open}

        </button>

      ),

    },

  ];



  return (

    <section

      className={styles.panel}

      aria-label={BUDGET_SIMULATION_COPY.sourceEnvelopes.caption}

      data-source-trust-envelopes-table

      data-budget-elevated-panel="true"

    >

      <Table

        caption={BUDGET_SIMULATION_COPY.sourceEnvelopes.caption}

        columns={columns}

        rows={rows}

        state="populated"

        density="standard"

        getRowKey={(row) => row.envelopeId}

        onRowActivate={(row) => navigate(buildClaimTrustDrawerHref(row.envelopeId))}

      />

    </section>

  );

}


