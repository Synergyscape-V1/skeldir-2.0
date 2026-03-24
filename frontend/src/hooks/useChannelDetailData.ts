import { useEffect, useState } from "react";
import type { ChannelDetailState, ChannelDetailScenario, DateRangeValue } from "../types/channel";
import type { ChannelDatasetVariant } from "../mocks/channelDetailFixtures";
import { getChannelDetailHarnessState } from "../mocks/channelDetailFixtures";

export function useChannelDetailData(
  channelId: string,
  dateRange: DateRangeValue,
  scenario: ChannelDetailScenario,
  dataset: ChannelDatasetVariant
): ChannelDetailState & { notFound: boolean; updating: boolean; retry: () => void } {
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState(() =>
    getChannelDetailHarnessState(scenario, channelId, dateRange, dataset)
  );

  useEffect(() => {
    const delay = scenario === "loading" ? 600 : scenario === "updating" ? 400 : 60;
    const id = window.setTimeout(() => {
      setState(getChannelDetailHarnessState(scenario, channelId, dateRange, dataset));
    }, delay);
    return () => window.clearTimeout(id);
  }, [channelId, dateRange, scenario, dataset, nonce]);

  return {
    data: state.data,
    loading: state.loading,
    error: state.error,
    notFound: state.notFound,
    updating: state.updating,
    retry: () => setNonce((v) => v + 1),
  };
}
