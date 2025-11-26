import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { User } from 'lucide-react';

interface UserInfoCardProps {
  username: string;
  email: string;
  lastLogin?: string;
}

export function UserInfoCard({ username, email, lastLogin }: UserInfoCardProps) {
  return (
    <Card 
      className="shadow-xl" 
      style={{ 
        backgroundColor: 'hsl(var(--brand-alice) / 0.6)',
        borderColor: 'hsl(var(--brand-jordy) / 0.3)'
      }} 
      data-testid="card-user-info"
    >
      <CardHeader>
        <CardTitle className="flex items-center space-x-2" style={{ color: 'hsl(var(--brand-cool-black))' }}>
          <User className="w-5 h-5" />
          <span>Profile Information</span>
        </CardTitle>
        <CardDescription style={{ color: 'hsl(var(--brand-cool-black) / 0.7)' }}>
          Your account details and recent activity
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium" style={{ color: 'hsl(var(--brand-cool-black) / 0.8)' }}>Username</label>
            <p className="text-lg font-medium" style={{ color: 'hsl(var(--brand-cool-black))' }} data-testid="text-username">
              {username}
            </p>
          </div>
          
          <div>
            <label className="text-sm font-medium" style={{ color: 'hsl(var(--brand-cool-black) / 0.8)' }}>Email</label>
            <p className="text-lg font-medium" style={{ color: 'hsl(var(--brand-cool-black))' }} data-testid="text-email">
              {email}
            </p>
          </div>
          
          {lastLogin && (
            <div className="md:col-span-2">
              <label className="text-sm font-medium" style={{ color: 'hsl(var(--brand-cool-black) / 0.8)' }}>Last Login</label>
              <p className="text-lg font-medium" style={{ color: 'hsl(var(--brand-cool-black))' }} data-testid="text-last-login">
                {new Date(lastLogin).toLocaleString()}
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
