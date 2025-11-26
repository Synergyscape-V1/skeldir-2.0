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
      className="shadow-xl" 
      style={{ 
        backgroundColor: 'hsl(var(--brand-alice) / 0.6)',
        borderColor: 'hsl(var(--brand-jordy) / 0.3)'
      }}
    >
      <CardHeader>
        <CardTitle style={{ color: 'hsl(var(--brand-cool-black))' }}>Recent Activity</CardTitle>
        <CardDescription style={{ color: 'hsl(var(--brand-cool-black) / 0.7)' }}>
          Your recent account activity
        </CardDescription>
      </CardHeader>
      <CardContent>
        {status === 'success' && data.length > 0 ? (
          <div className="space-y-2" data-testid="list-activity">
            {data.map(item => (
              <div key={item.id} className="p-3 rounded-md" style={{ backgroundColor: 'hsl(var(--brand-alice) / 0.5)' }}>
                <p className="font-medium" style={{ color: 'hsl(var(--brand-cool-black))' }}>{item.action}</p>
                <p className="text-sm" style={{ color: 'hsl(var(--brand-cool-black) / 0.7)' }}>{new Date(item.time).toLocaleString()}</p>
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
