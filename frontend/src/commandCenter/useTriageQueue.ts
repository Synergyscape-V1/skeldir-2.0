import { useSyncExternalStore } from 'react';
import {
  getTriageQueueSnapshot,
  subscribeTriageQueue,
  type TriageQueueSnapshot,
} from './triageQueueStore';

export function useTriageQueue(): TriageQueueSnapshot {
  return useSyncExternalStore(subscribeTriageQueue, getTriageQueueSnapshot, getTriageQueueSnapshot);
}
