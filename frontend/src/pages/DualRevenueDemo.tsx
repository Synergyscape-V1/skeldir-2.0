import { useState } from 'react';
import DualRevenueCard from '@/components/DualRevenueCard';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

const scenarios = [
  {
    name: 'Balanced Split (68/32)',
    data: {
      verifiedRevenue: 125340,
      unverifiedRevenue: 58960,
      totalRevenue: 184300,
      verifiedPercentage: 68,
      unverifiedPercentage: 32,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    }
  },
  {
    name: 'Extreme Split (99/1)',
    data: {
      verifiedRevenue: 198000,
      unverifiedRevenue: 2000,
      totalRevenue: 200000,
      verifiedPercentage: 99,
      unverifiedPercentage: 1,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    }
  },
  {
    name: 'Small Percentages',
    data: {
      verifiedRevenue: 500,
      unverifiedRevenue: 300,
      totalRevenue: 800,
      verifiedPercentage: 0.625,
      unverifiedPercentage: 0.375,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    }
  },
  {
    name: 'Large Numbers ($10M+)',
    data: {
      verifiedRevenue: 7500000,
      unverifiedRevenue: 3200000,
      totalRevenue: 10700000,
      verifiedPercentage: 70.09,
      unverifiedPercentage: 29.91,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    }
  },
  {
    name: 'Zero Revenue',
    data: {
      verifiedRevenue: 0,
      unverifiedRevenue: 0,
      totalRevenue: 0,
      verifiedPercentage: 0,
      unverifiedPercentage: 0,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    }
  },
  {
    name: 'Only Verified',
    data: {
      verifiedRevenue: 85000,
      unverifiedRevenue: 0,
      totalRevenue: 85000,
      verifiedPercentage: 100,
      unverifiedPercentage: 0,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    }
  },
  {
    name: 'Only Unverified',
    data: {
      verifiedRevenue: 0,
      unverifiedRevenue: 45000,
      totalRevenue: 45000,
      verifiedPercentage: 0,
      unverifiedPercentage: 100,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    }
  },
  {
    name: 'With Polling (30s)',
    polling: true,
    data: {
      verifiedRevenue: 50000,
      unverifiedRevenue: 30000,
      totalRevenue: 80000,
      verifiedPercentage: 62.5,
      unverifiedPercentage: 37.5,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    }
  }
];

export default function DualRevenueDemo() {
  const [selectedScenario, setSelectedScenario] = useState(0);
  const [pollingData, setPollingData] = useState(scenarios[7].data);

  const simulatePolling = async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    
    const variance = 0.1;
    const verifiedChange = (Math.random() - 0.5) * variance * pollingData.verifiedRevenue;
    const unverifiedChange = (Math.random() - 0.5) * variance * pollingData.unverifiedRevenue;
    
    const newVerified = Math.max(0, pollingData.verifiedRevenue + verifiedChange);
    const newUnverified = Math.max(0, pollingData.unverifiedRevenue + unverifiedChange);
    const newTotal = newVerified + newUnverified;
    
    const newData = {
      verifiedRevenue: newVerified,
      unverifiedRevenue: newUnverified,
      totalRevenue: newTotal,
      verifiedPercentage: newTotal > 0 ? (newVerified / newTotal) * 100 : 0,
      unverifiedPercentage: newTotal > 0 ? (newUnverified / newTotal) * 100 : 0,
      timestamp: new Date().toISOString(),
      currency: 'USD' as const
    };
    
    setPollingData(newData);
    return newData;
  };

  const currentScenario = scenarios[selectedScenario];

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <div>
          <h1 className="text-4xl font-bold mb-2" style={{ color: 'var(--brand-cool-black)' }}>
            DualRevenueCard Component Demo
          </h1>
          <p className="text-lg" style={{ color: 'var(--brand-cool-black, #092F64)' }}>
            Comprehensive demonstration of all features and edge cases
          </p>
        </div>

        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4" style={{ color: 'var(--brand-tufts)' }}>
            Select Scenario
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {scenarios.map((scenario, index) => (
              <Button
                key={index}
                onClick={() => setSelectedScenario(index)}
                variant={selectedScenario === index ? 'default' : 'outline'}
                className="w-full"
                data-testid={`button-scenario-${index}`}
              >
                {scenario.name}
              </Button>
            ))}
          </div>
        </Card>

        <div>
          <h2 className="text-2xl font-semibold mb-4" style={{ color: 'var(--brand-tufts)' }}>
            Current Scenario: {currentScenario.name}
          </h2>
          
          {currentScenario.polling ? (
            <DualRevenueCard 
              data={pollingData}
              onPoll={simulatePolling}
              pollingInterval={30000}
              currency="USD"
            />
          ) : (
            <DualRevenueCard 
              data={currentScenario.data}
              currency={currentScenario.data.currency}
            />
          )}
        </div>

        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4" style={{ color: 'var(--brand-tufts)' }}>
            Features Demonstrated
          </h2>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-semibold mb-2" style={{ color: 'var(--brand-cool-black)' }}>✅ Core Features</h3>
              <ul className="space-y-1 text-sm" style={{ color: 'var(--brand-cool-black, #092F64)' }}>
                <li>• Glass morphism UI with backdrop blur</li>
                <li>• Verified/Unverified section distinction</li>
                <li>• Circular progress rings with animations</li>
                <li>• Comparison bar visualization</li>
                <li>• Responsive grid layout (2-col → 1-col)</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-2" style={{ color: 'var(--brand-cool-black)' }}>✅ Animations</h3>
              <ul className="space-y-1 text-sm" style={{ color: 'var(--brand-cool-black, #092F64)' }}>
                <li>• Card entrance: 400ms slide + fade</li>
                <li>• Verified icon: 500ms elastic bounce</li>
                <li>• Unverified icon: 400ms fade-in</li>
                <li>• Count-up revenue with easing</li>
                <li>• Progress rings: 1000ms animation</li>
                <li>• Comparison bars: 800ms grow</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-2" style={{ color: 'var(--brand-cool-black)' }}>✅ Edge Cases</h3>
              <ul className="space-y-1 text-sm" style={{ color: 'var(--brand-cool-black, #092F64)' }}>
                <li>• Zero revenue handling</li>
                <li>• Single-section scenarios</li>
                <li>• Extreme percentage splits (99/1)</li>
                <li>• Large numbers ($10M+) with K/M formatting</li>
                <li>• Small percentages (&lt;1%) display</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-2" style={{ color: 'var(--brand-cool-black)' }}>✅ Advanced</h3>
              <ul className="space-y-1 text-sm" style={{ color: 'var(--brand-cool-black, #092F64)' }}>
                <li>• Polling with 30s interval</li>
                <li>• Stale data indicator (&gt;2 min)</li>
                <li>• Loading skeleton with shimmer</li>
                <li>• Error states with circuit breaker</li>
                <li>• ARIA labels for accessibility</li>
                <li>• Prefers-reduced-motion support</li>
              </ul>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4" style={{ color: 'var(--brand-tufts)' }}>
            Technical Specifications
          </h2>
          <div className="space-y-2 text-sm font-mono" style={{ color: 'var(--brand-cool-black, #092F64)' }}>
            <p>• Component Size: ~300 lines (includes all features)</p>
            <p>• GPU Accelerated: transform & opacity only</p>
            <p>• Animations: cubic-bezier(0.4, 0, 0.2, 1)</p>
            <p>• Responsive: Mobile (0-768px), Desktop (768px+)</p>
            <p>• Accessibility: WCAG AA compliant, ARIA attributes</p>
            <p>• Browser Support: Chrome, Firefox, Safari, Edge</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
