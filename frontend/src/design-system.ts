/**
 * Design System Entry Point (D0 → D1 → D2)
 *
 * This file serves as the hermetic export surface for the Skeldir Design System.
 * It enables the design system to be built as an independent library,
 * completely isolated from application-layer concerns (API, routing, business logic).
 *
 * Architectural Layers:
 * - D0: Token Foundation (cn utility, design tokens)
 * - D1: Atomic Primitives (shadcn/ui components)
 * - D2: Composite Assemblies (reusable composite components)
 *
 * Build Target: npm run build:design-system
 * Scope: Independent of src/api/*, src/pages/* (except harnesses)
 */

// ============================================================================
// D0 - Token Foundation
// ============================================================================

export { cn } from '@/lib/utils';

// ============================================================================
// D1 - Atomic Primitives (Actively Used in Production)
// ============================================================================

export { Badge, badgeVariants } from '@/components/ui/badge';
export type { BadgeProps } from '@/components/ui/badge';

export { Button, buttonVariants } from '@/components/ui/button';
export type { ButtonProps } from '@/components/ui/button';

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent } from '@/components/ui/card';

export { Input } from '@/components/ui/input';
export type { InputProps } from '@/components/ui/input';

export { Label } from '@/components/ui/label';

export { Separator } from '@/components/ui/separator';

export { Checkbox } from '@/components/ui/checkbox';

export { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';

export { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

export { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';

export { Textarea } from '@/components/ui/textarea';

export { Toast, ToastAction, ToastClose, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from '@/components/ui/toast';

export { Toaster } from '@/components/ui/toaster';

export { RequestStatus } from '@/components/ui/request-status';

// ============================================================================
// D2 - Composite Assemblies (Authoritative Exports)
// ============================================================================

// Re-export all D2 composites from the canonical barrel
export {
  // Type exports
  type DataCompositeStatus,

  // Fixture exports
  activitySectionFixtures,
  dataConfidenceBarFixtures,
  userInfoCardFixtures,
  allDataBearingFixtures,
  stateKeys,

  // Component exports
  ActivitySection,
  UserInfoCard,
  DataConfidenceBar,
  ConfidenceScoreBadge,
  BulkActionModal,
  BulkActionToolbar,
  ErrorBanner,
  ErrorBannerContainer,
  ErrorBannerProvider,
} from '@/components/composites';

// ============================================================================
// Design System Metadata
// ============================================================================

export const DESIGN_SYSTEM_VERSION = '1.0.0';
export const DESIGN_SYSTEM_LAYERS = {
  D0: 'Token Foundation',
  D1: 'Atomic Primitives',
  D2: 'Composite Assemblies',
} as const;
