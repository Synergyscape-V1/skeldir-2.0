import { PlatformConnectionIcon } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Link } from 'wouter';

export default function EmptyState() {
  return (
    <div 
      className="flex flex-col items-center justify-center mx-auto rounded-lg border border-gray-200"
      style={{ 
        width: '300px', 
        height: '200px',
        backgroundColor: '#F8FAFC' 
      }}
      data-testid="empty-state-platforms"
    >
      <div className="mb-4">
        <PlatformConnectionIcon 
          size={64}
          aria-label="No platforms connected"
          data-testid="icon-connection"
        />
      </div>
      <h3 
        className="text-base font-semibold mb-2" 
        style={{ color: '#1A202C' }}
        data-testid="heading-empty-state"
      >
        No Platforms Connected
      </h3>
      <p 
        className="text-sm text-center mb-4 px-6" 
        style={{ color: '#6B7280' }}
        data-testid="text-empty-state"
      >
        Connect payment processors to monitor revenue verification
      </p>
      <Link href="/integration-settings">
        <Button 
          variant="default" 
          size="sm"
          data-testid="button-connect-platform"
        >
          Connect Platform
        </Button>
      </Link>
    </div>
  );
}
