/**
 * Channel Detail Route — wires the final Single Channel Detail page
 * into the app router.
 *
 * Currently uses mock data (MOCK_CHANNEL_DATA) since the API endpoint
 * is not yet available. When the backend delivers /api/v1/channels/:channelId/detail,
 * replace the mock state with a useQuery hook.
 *
 * The "Meta Ads" branding is applied via the mock data channel name.
 */

import React from 'react';
import { ChannelDetailPage } from './channel-detail/ChannelDetailPage';
import type { ChannelDetailState } from '@/explorations/channel-detail/shared/types';
import { MOCK_CHANNEL_DATA } from '@/explorations/channel-detail/shared/mock-data';

// Override channel name to "Meta Ads" per branding mandate
const metaAdsData = {
  ...MOCK_CHANNEL_DATA,
  channel: {
    ...MOCK_CHANNEL_DATA.channel,
    id: 'meta',
    name: 'Meta Ads',
  },
};

const ChannelDetailRoute: React.FC = () => {
  // TODO: Replace with useQuery when API is available:
  // const { data, isLoading, error } = useQuery({ queryKey: ['channel', channelId], queryFn: ... })
  const state: ChannelDetailState = {
    status: 'ready',
    data: metaAdsData,
  };

  return <ChannelDetailPage state={state} />;
};

export default ChannelDetailRoute;
