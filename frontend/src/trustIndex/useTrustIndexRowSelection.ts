import { useCallback, useState } from 'react';

export interface TrustIndexRowSelection {
  selectedIds: ReadonlySet<string>;
  selectedCount: number;
  isSelected: (envelopeId: string) => boolean;
  allVisibleSelected: boolean;
  someVisibleSelected: boolean;
  toggleRow: (envelopeId: string) => void;
  toggleAllVisible: () => void;
}

export function useTrustIndexRowSelection(visibleEnvelopeIds: string[]): TrustIndexRowSelection {
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(() => new Set());

  const isSelected = useCallback((envelopeId: string) => selectedIds.has(envelopeId), [selectedIds]);

  const allVisibleSelected =
    visibleEnvelopeIds.length > 0 && visibleEnvelopeIds.every((id) => selectedIds.has(id));

  const someVisibleSelected = visibleEnvelopeIds.some((id) => selectedIds.has(id));

  const toggleRow = useCallback((envelopeId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(envelopeId)) next.delete(envelopeId);
      else next.add(envelopeId);
      return next;
    });
  }, []);

  const toggleAllVisible = useCallback(() => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (visibleEnvelopeIds.every((id) => next.has(id))) {
        for (const id of visibleEnvelopeIds) next.delete(id);
      } else {
        for (const id of visibleEnvelopeIds) next.add(id);
      }
      return next;
    });
  }, [visibleEnvelopeIds]);

  const selectedCount = selectedIds.size;

  return {
    selectedIds,
    selectedCount,
    isSelected,
    allVisibleSelected,
    someVisibleSelected,
    toggleRow,
    toggleAllVisible,
  };
}
