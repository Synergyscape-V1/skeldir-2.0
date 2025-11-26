/**
 * Channel Performance Dashboard Component
 * Displays attribution channel performance metrics from Mockoon API
 * Uses: use-channel-performance hook (Port 4011)
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useChannelPerformance } from '@/hooks/use-channel-performance';
import { TrendingUp, DollarSign, Target, Award } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';

export interface ChannelPerformanceDashboardProps {
  className?: string;
}

export default function ChannelPerformanceDashboard({ className }: ChannelPerformanceDashboardProps) {
  const { data: channels, isLoading, error } = useChannelPerformance();

  if (error) {
    return (
      <Card className={className} data-testid="card-channel-performance-error">
        <CardHeader>
          <CardTitle>Channel Performance</CardTitle>
          <CardDescription>Error loading channel data: {error.message}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (isLoading || !channels) {
    return (
      <Card className={className} data-testid="card-channel-performance-loading">
        <CardHeader>
          <CardTitle>Channel Performance</CardTitle>
          <CardDescription>Loading channel data...</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  const sortedChannels = [...channels].sort((a, b) => b.total_revenue - a.total_revenue);

  return (
    <Card className={className} data-testid="card-channel-performance">
      <CardHeader>
        <CardTitle>Channel Performance</CardTitle>
        <CardDescription>
          Attribution performance across marketing channels
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {sortedChannels.map((channel) => (
          <Card
            key={channel.channel}
            className="p-4"
            data-testid={`card-channel-${channel.channel}`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-md bg-primary/10">
                  <Target className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h4 className="font-semibold text-foreground capitalize" data-testid={`text-channel-name-${channel.channel}`}>
                    {channel.channel.replace(/_/g, ' ')}
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    {channel.model_type} attribution
                  </p>
                </div>
              </div>
              <Badge variant={channel.verification_rate > 0.8 ? 'default' : 'secondary'} data-testid={`badge-verification-${channel.channel}`}>
                {(channel.verification_rate * 100).toFixed(0)}% verified
              </Badge>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="flex items-center gap-1.5 text-muted-foreground text-xs mb-1">
                  <DollarSign className="w-3.5 h-3.5" />
                  <span>Total Revenue</span>
                </div>
                <p className="font-semibold text-foreground" data-testid={`text-total-revenue-${channel.channel}`}>
                  {formatCurrency(channel.total_revenue)}
                </p>
              </div>

              <div>
                <div className="flex items-center gap-1.5 text-muted-foreground text-xs mb-1">
                  <Award className="w-3.5 h-3.5" />
                  <span>Verified Revenue</span>
                </div>
                <p className="font-semibold text-green-600 dark:text-green-400" data-testid={`text-verified-revenue-${channel.channel}`}>
                  {formatCurrency(channel.verified_revenue)}
                </p>
              </div>

              <div>
                <div className="flex items-center gap-1.5 text-muted-foreground text-xs mb-1">
                  <TrendingUp className="w-3.5 h-3.5" />
                  <span>Conversions</span>
                </div>
                <p className="font-semibold text-foreground" data-testid={`text-conversions-${channel.channel}`}>
                  {channel.conversion_count.toLocaleString()}
                </p>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-border">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Avg Confidence</span>
                <span className="font-medium text-foreground" data-testid={`text-confidence-${channel.channel}`}>
                  {(channel.avg_confidence * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </Card>
        ))}

        {channels.length === 0 && (
          <div className="text-center py-8 text-muted-foreground" data-testid="text-no-channels">
            No channel data available
          </div>
        )}
      </CardContent>
    </Card>
  );
}
