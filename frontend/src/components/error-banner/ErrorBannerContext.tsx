import { createContext } from 'react';
import type { ErrorBannerContext } from '@/types/error-banner';

export const ErrorBannerContextInstance = createContext<ErrorBannerContext | null>(null);
