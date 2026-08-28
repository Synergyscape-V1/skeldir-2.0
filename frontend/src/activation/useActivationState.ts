import { useEffect, useState } from 'react';
import { getActivationState, subscribeActivationState } from './activationStore';
import type { ActivationState } from './types';

export function useActivationState(): ActivationState {
  const [state, setState] = useState<ActivationState>(getActivationState());

  useEffect(() => subscribeActivationState(setState), []);

  return state;
}
