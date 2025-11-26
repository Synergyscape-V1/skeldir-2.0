/**
 * Model Comparison Chart Component
 * Compares attribution models (first-touch, last-touch, linear, etc.)
 * Uses: use-model-comparison hook (Port 4011)
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useModelComparison } from '@/hooks/use-model-comparison';
import { BarChart3, DollarSign } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';

export interface ModelComparisonChartProps {
  className?: string;
}

export default function ModelComparisonChart({ className }: ModelComparisonChartProps) {
  const { data: models, isLoading, error } = useModelComparison();

  if (error) {
    return (
      <Card className={className} data-testid="card-model-comparison-error">
        <CardHeader>
          <CardTitle>Attribution Model Comparison</CardTitle>
          <CardDescription>Error loading model data: {error.message}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (isLoading || !models) {
    return (
      <Card className={className} data-testid="card-model-comparison-loading">
        <CardHeader>
          <CardTitle>Attribution Model Comparison</CardTitle>
          <CardDescription>Loading model comparison...</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  const sortedModels = [...models].sort((a, b) => b.total_revenue - a.total_revenue);
  const maxRevenue = sortedModels[0]?.total_revenue || 1;

  return (
    <Card className={className} data-testid="card-model-comparison">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          Attribution Model Comparison
        </CardTitle>
        <CardDescription>
          Compare how different attribution models allocate revenue across channels
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {sortedModels.map((model) => {
          const channels = Object.entries(model.channel_allocations).sort(
            ([, a], [, b]) => b - a
          );
          const revenuePercent = (model.total_revenue / maxRevenue) * 100;

          return (
            <Card key={model.model_type} className="p-4" data-testid={`card-model-${model.model_type}`}>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="font-semibold text-foreground capitalize" data-testid={`text-model-name-${model.model_type}`}>
                    {model.model_type.replace(/_/g, ' ')}
                  </h4>
                  <div className="flex items-center gap-2 mt-1">
                    <DollarSign className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground" data-testid={`text-model-revenue-${model.model_type}`}>
                      {formatCurrency(model.total_revenue)}
                    </span>
                  </div>
                </div>
                <Badge variant="secondary" data-testid={`badge-model-percent-${model.model_type}`}>
                  {revenuePercent.toFixed(0)}% of max
                </Badge>
              </div>

              <div className="space-y-2">
                <div className="text-xs text-muted-foreground font-medium mb-1.5">
                  Channel Allocation
                </div>
                {channels.map(([channel, allocation]) => {
                  const allocationPercent = (allocation / model.total_revenue) * 100;
                  
                  return (
                    <div key={channel} className="space-y-1" data-testid={`channel-allocation-${model.model_type}-${channel}`}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground capitalize">
                          {channel.replace(/_/g, ' ')}
                        </span>
                        <span className="font-medium text-foreground">
                          {formatCurrency(allocation)} ({allocationPercent.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all duration-300"
                          style={{ width: `${allocationPercent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          );
        })}

        {models.length === 0 && (
          <div className="text-center py-8 text-muted-foreground" data-testid="text-no-models">
            No model comparison data available
          </div>
        )}
      </CardContent>
    </Card>
  );
}
