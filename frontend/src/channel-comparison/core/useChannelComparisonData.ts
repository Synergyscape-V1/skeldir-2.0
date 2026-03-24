import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { DateRangeValue } from "../../types/channel";
import type {
  ChannelComparisonUiState,
  ChannelComparisonViewState,
  ComparisonPanelError,
  ComparisonScenario,
} from "../../types/comparison";
import { VALID_DATE_RANGES } from "./constants";
import { defaultSelectedIds, fetchAvailableChannelsMock, fetchChannelDetailMock } from "./mockApi";
import { buildDerivedMetrics, computeBudgetRecommendation, computeWinner } from "./logic";

export interface UseChannelComparisonDataOptions {
  scenario?: ComparisonScenario;
  uiState?: ChannelComparisonUiState;
  initialDateRange?: DateRangeValue;
  selectedChannels?: string[];
}

export interface UseChannelComparisonDataReturn {
  state: ChannelComparisonViewState;
  addChannel: (channelId: string) => void;
  addManualChannel: (channelId: string) => void;
  removeChannel: (channelId: string) => void;
  retryChannel: (channelId: string) => void;
  retryGlobal: () => void;
  setDateRange: (range: DateRangeValue) => void;
}

function arraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let index = 0; index < a.length; index += 1) {
    if (a[index] !== b[index]) return false;
  }
  return true;
}

function normalizeUiState(
  explicit: ChannelComparisonUiState | undefined,
  scenario: ComparisonScenario
): ChannelComparisonUiState {
  if (explicit) return explicit;
  if (scenario === "loading") return "loading";
  if (scenario === "empty") return "empty";
  if (scenario === "error") return "error_panel";
  return "populated";
}

function toError(message: string, correlationId: string | null = null): ComparisonPanelError {
  return { message, correlationId };
}

function parseDateRange(searchParams: URLSearchParams, fallback: DateRangeValue): DateRangeValue {
  const value = searchParams.get("date_range");
  if (!value) return fallback;
  if (!VALID_DATE_RANGES.includes(value as DateRangeValue)) return fallback;
  return value as DateRangeValue;
}

function parseChannelIds(searchParams: URLSearchParams, fallback: string[]): string[] {
  const value = searchParams.get("channels");
  if (!value) return fallback;
  return value.split(",").map((id) => id.trim()).filter(Boolean).slice(0, 4);
}

export function useChannelComparisonData({
  scenario = "default",
  uiState,
  initialDateRange = "last_30_days",
  selectedChannels,
}: UseChannelComparisonDataOptions = {}): UseChannelComparisonDataReturn {
  const [searchParams, setSearchParams] = useSearchParams();
  const resolvedUiState = normalizeUiState(uiState, scenario);
  const fallbackIds = useMemo(
    () => selectedChannels?.slice(0, 4) ?? defaultSelectedIds(scenario),
    [scenario, selectedChannels]
  );
  const searchParamString = searchParams.toString();
  const [selectedChannelIds, setSelectedChannelIds] = useState<string[]>(() =>
    parseChannelIds(searchParams, fallbackIds)
  );
  const [dateRange, setDateRangeState] = useState<DateRangeValue>(() =>
    parseDateRange(searchParams, initialDateRange)
  );

  const [availableChannels, setAvailableChannels] = useState<ChannelComparisonViewState["availableChannels"]>([]);
  const [availableChannelsError, setAvailableChannelsError] = useState<ComparisonPanelError | null>(null);
  const [channelData, setChannelData] = useState<ChannelComparisonViewState["channelData"]>({});
  const [loading, setLoading] = useState<ChannelComparisonViewState["loading"]>({});
  const [errors, setErrors] = useState<ChannelComparisonViewState["errors"]>({});
  const [requestNonce, setRequestNonce] = useState(0);

  const updateQuery = useCallback(
    (ids: string[], range: DateRangeValue) => {
      const next = new URLSearchParams();
      if (ids.length > 0) next.set("channels", ids.join(","));
      next.set("date_range", range);
      setSearchParams(next);
    },
    [setSearchParams]
  );

  useEffect(() => {
    const params = new URLSearchParams(searchParamString);
    const idsFromParams = parseChannelIds(params, fallbackIds);
    const nextIds = resolvedUiState === "empty" ? [] : idsFromParams;
    const nextDateRange = parseDateRange(params, initialDateRange);
    setSelectedChannelIds((previous) => (arraysEqual(previous, nextIds) ? previous : nextIds));
    setDateRangeState((previous) => (previous === nextDateRange ? previous : nextDateRange));
  }, [fallbackIds, initialDateRange, resolvedUiState, scenario, searchParamString]);

  useEffect(() => {
    let active = true;
    const shouldFail = resolvedUiState === "error_global";
    fetchAvailableChannelsMock(shouldFail)
      .then((response) => {
        if (!active) return;
        setAvailableChannels(response);
        setAvailableChannelsError(null);
      })
      .catch((error: Error) => {
        if (!active) return;
        setAvailableChannels([]);
        setAvailableChannelsError(toError(error.message, "corr-channels-500"));
      });
    return () => {
      active = false;
    };
  }, [resolvedUiState, requestNonce]);

  useEffect(() => {
    let active = true;
    if (resolvedUiState === "empty") {
      setChannelData({});
      setLoading({});
      setErrors({});
      return () => {
        active = false;
      };
    }

    if (selectedChannelIds.length === 0) {
      setChannelData({});
      setLoading({});
      setErrors({});
      return () => {
        active = false;
      };
    }

    const loadingMap = Object.fromEntries(selectedChannelIds.map((id) => [id, true]));
    setLoading(loadingMap);
    setErrors(Object.fromEntries(selectedChannelIds.map((id) => [id, null])));

    const panelErrorTarget = resolvedUiState === "error_panel" ? selectedChannelIds[selectedChannelIds.length - 1] : null;
    const forceLoading = resolvedUiState === "loading";
    const noWinnerMode = scenario === "no_winner";

    Promise.allSettled(
      selectedChannelIds.map(async (id) => {
        const shouldFail = panelErrorTarget === id;
        const data = await fetchChannelDetailMock(id, dateRange, { shouldFail, noWinnerMode });
        return { id, data };
      })
    )
      .then((rows) => {
        if (!active) return;
        if (forceLoading) {
          setChannelData({});
          setLoading(Object.fromEntries(selectedChannelIds.map((id) => [id, true])));
          return;
        }
        const nextChannelData: ChannelComparisonViewState["channelData"] = {};
        const nextLoading: ChannelComparisonViewState["loading"] = {};
        const nextErrors: ChannelComparisonViewState["errors"] = {};
        rows.forEach((row, index) => {
          const id = selectedChannelIds[index];
          nextLoading[id] = false;
          if (row.status === "fulfilled") {
            nextChannelData[id] = row.value.data;
            nextErrors[id] = null;
            return;
          }
          nextErrors[id] = toError(row.reason?.message ?? "Failed to load channel detail", "corr-compare-500");
        });
        setChannelData(nextChannelData);
        setLoading(nextLoading);
        setErrors(nextErrors);
      });

    return () => {
      active = false;
    };
  }, [selectedChannelIds, dateRange, resolvedUiState, scenario, requestNonce]);

  const loadedChannels = useMemo(
    () => selectedChannelIds.map((id) => channelData[id]).filter(Boolean),
    [selectedChannelIds, channelData]
  );
  const winner = useMemo(() => computeWinner(loadedChannels), [loadedChannels]);
  const budgetRecommendation = useMemo(
    () => computeBudgetRecommendation(loadedChannels, winner),
    [loadedChannels, winner]
  );
  const derivedByChannelId = useMemo(() => buildDerivedMetrics(loadedChannels), [loadedChannels]);

  const addChannel = useCallback(
    (channelId: string) => {
      if (selectedChannelIds.includes(channelId)) return;
      if (selectedChannelIds.length >= 4) return;
      const next = [...selectedChannelIds, channelId];
      setSelectedChannelIds(next);
      updateQuery(next, dateRange);
    },
    [selectedChannelIds, updateQuery, dateRange]
  );

  const addManualChannel = useCallback(
    (channelId: string) => {
      const normalized = channelId.trim();
      if (!normalized) return;
      addChannel(normalized);
    },
    [addChannel]
  );

  const removeChannel = useCallback(
    (channelId: string) => {
      const next = selectedChannelIds.filter((id) => id !== channelId);
      setSelectedChannelIds(next);
      updateQuery(next, dateRange);
    },
    [selectedChannelIds, updateQuery, dateRange]
  );

  const retryChannel = useCallback(
    (channelId: string) => {
      if (!selectedChannelIds.includes(channelId)) return;
      setRequestNonce((value) => value + 1);
    },
    [selectedChannelIds]
  );

  const retryGlobal = useCallback(() => {
    setRequestNonce((value) => value + 1);
  }, []);

  const setDateRange = useCallback(
    (range: DateRangeValue) => {
      if (range === dateRange) return;
      setDateRangeState(range);
      updateQuery(selectedChannelIds, range);
    },
    [dateRange, selectedChannelIds, updateQuery]
  );

  const state: ChannelComparisonViewState = {
    selectedChannelIds: resolvedUiState === "empty" ? [] : selectedChannelIds,
    dateRange,
    availableChannels,
    availableChannelsError,
    channelData,
    loading,
    errors,
    winner,
    budgetRecommendation,
    derivedByChannelId,
  };

  return {
    state,
    addChannel,
    addManualChannel,
    removeChannel,
    retryChannel,
    retryGlobal,
    setDateRange,
  };
}
