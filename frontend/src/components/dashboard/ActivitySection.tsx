import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { RequestStatus } from '@/components/ui/request-status';

interface ActivityItem {
  id: number;
  action: string;
  time: string;
}

interface ActivitySectionProps {
  status: 'loading' | 'error' | 'empty' | 'success';
  data: ActivityItem[];
  onRetry: () => void;
}

export function ActivitySection({ status, data, onRetry }: ActivitySectionProps) {
  return (
    <Card
      className="shadow-xl bg-brand-alice/60 border-brand-jordy/30"
    >
      <CardHeader>
        <CardTitle className="text-brand-cool-black">Recent Activity</CardTitle>
        <CardDescription className="text-brand-cool-black/70">
          Your recent account activity
        </CardDescription>
      </CardHeader>
      <CardContent>
        {status === 'success' && data.length > 0 ? (
          <div className="space-y-2" data-testid="list-activity">
            {data.map(item => (
              <div key={item.id} className="p-3 rounded-md bg-brand-alice/50">
                <p className="font-medium text-brand-cool-black">{item.action}</p>
                <p className="text-sm text-brand-cool-black/70">{new Date(item.time).toLocaleString()}</p>
              </div>
            ))}
          </div>
        ) : (
          <RequestStatus 
            {...(status === 'error' ? {
              status: 'error' as const,
              message: 'Failed to load activity',
              onRetry,
              skeletonVariant: 'activityList' as const
            } : status === 'empty' ? {
              status: 'empty' as const,
              message: 'No recent activity found',
              skeletonVariant: 'activityList' as const
            } : {
              status: 'loading' as const,
              skeletonVariant: 'activityList' as const
            })}
          />
        )}
      </CardContent>
    </Card>
  );
}
