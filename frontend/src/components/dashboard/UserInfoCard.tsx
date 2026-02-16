import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { RequestStatus } from '@/components/ui/request-status';
import { User } from 'lucide-react';

/**
 * D2-P3 State Contract: supports loading/empty/error/success via normalized status prop.
 * Non-success states delegate to RequestStatus (D1 substrate).
 */
interface UserInfoCardProps {
  /** Normalized state contract — drives render branch selection */
  status: 'loading' | 'error' | 'empty' | 'success';
  username: string;
  email: string;
  lastLogin?: string;
  /** Error recovery callback — required for error state, ignored otherwise */
  onRetry: () => void;
}

export function UserInfoCard({ status, username, email, lastLogin, onRetry }: UserInfoCardProps) {
  return (
    <Card
      className="shadow-xl bg-brand-alice/60 border-brand-jordy/30"
      data-testid="card-user-info"
      data-status={status}
    >
      <CardHeader>
        <CardTitle className="flex items-center space-x-2 text-brand-cool-black">
          <User className="w-5 h-5" />
          <span>Profile Information</span>
        </CardTitle>
        <CardDescription className="text-brand-cool-black/70">
          Your account details and recent activity
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {status === 'success' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-brand-cool-black/80">Username</label>
              <p className="text-lg font-medium text-brand-cool-black" data-testid="text-username">
                {username}
              </p>
            </div>

            <div>
              <label className="text-sm font-medium text-brand-cool-black/80">Email</label>
              <p className="text-lg font-medium text-brand-cool-black" data-testid="text-email">
                {email}
              </p>
            </div>

            {lastLogin && (
              <div className="md:col-span-2">
                <label className="text-sm font-medium text-brand-cool-black/80">Last Login</label>
                <p className="text-lg font-medium text-brand-cool-black" data-testid="text-last-login">
                  {new Date(lastLogin).toLocaleString()}
                </p>
              </div>
            )}
          </div>
        ) : (
          <RequestStatus
            {...(status === 'error' ? {
              status: 'error' as const,
              message: 'Failed to load profile',
              onRetry,
              skeletonVariant: 'card' as const,
            } : status === 'empty' ? {
              status: 'empty' as const,
              message: 'No profile data available',
              skeletonVariant: 'card' as const,
            } : {
              status: 'loading' as const,
              skeletonVariant: 'card' as const,
            })}
          />
        )}
      </CardContent>
    </Card>
  );
}
