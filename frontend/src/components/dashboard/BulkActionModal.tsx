import { useState } from 'react';
import { AlertTriangle, CheckCircle, Flag, Archive, UserPlus } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import type { UnmatchedTransaction } from '@shared/schema';

interface BulkActionModalProps {
  action: string;
  selectedCount: number;
  selectedTransactions: UnmatchedTransaction[];
  onConfirm: (metadata?: any) => void;
  onCancel: () => void;
}

export function BulkActionModal({
  action,
  selectedCount,
  selectedTransactions,
  onConfirm,
  onCancel,
}: BulkActionModalProps) {
  const [notes, setNotes] = useState('');
  const [assignedUser, setAssignedUser] = useState('');
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const actionConfig = {
    mark_reviewed: {
      title: 'Mark as Reviewed',
      icon: CheckCircle,
      iconColor: 'text-green-600 dark:text-green-500',
      bgColor: 'bg-green-50 dark:bg-green-950/30',
      description: `Mark ${selectedCount} transaction${selectedCount !== 1 ? 's' : ''} as reviewed. These transactions will be considered verified and won't count toward variance.`,
      warningText: 'This action will update reconciliation status and may affect overall match percentage.',
      confirmButton: 'Mark as Reviewed',
      confirmColor: 'bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-800',
    },
    flag_investigation: {
      title: 'Flag for Investigation',
      icon: Flag,
      iconColor: 'text-amber-600 dark:text-amber-500',
      bgColor: 'bg-amber-50 dark:bg-amber-950/30',
      description: `Flag ${selectedCount} transaction${selectedCount !== 1 ? 's' : ''} for manual investigation. These will remain in the unmatched list until resolved.`,
      warningText: 'Flagged transactions require follow-up action before reconciliation can complete.',
      confirmButton: 'Flag Transactions',
      confirmColor: 'bg-amber-600 hover:bg-amber-700 dark:bg-amber-700 dark:hover:bg-amber-800',
    },
    exclude_variance: {
      title: 'Exclude from Variance Calculation',
      icon: Archive,
      iconColor: 'text-gray-600 dark:text-gray-400',
      bgColor: 'bg-gray-50 dark:bg-gray-950/30',
      description: `Exclude ${selectedCount} transaction${selectedCount !== 1 ? 's' : ''} from variance calculations. Use this for known exceptions or legacy data.`,
      warningText: 'Excluded transactions will not appear in future reconciliation reports.',
      confirmButton: 'Exclude Transactions',
      confirmColor: 'bg-gray-600 hover:bg-gray-700 dark:bg-gray-700 dark:hover:bg-gray-800',
    },
    assign_user: {
      title: 'Assign for Investigation',
      icon: UserPlus,
      iconColor: 'text-blue-600 dark:text-blue-400',
      bgColor: 'bg-blue-50 dark:bg-blue-950/30',
      description: `Assign ${selectedCount} transaction${selectedCount !== 1 ? 's' : ''} to a team member for investigation.`,
      warningText: 'Assigned user will receive a notification with transaction details.',
      confirmButton: 'Assign Transactions',
      confirmColor: 'bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800',
    },
  };

  const config = actionConfig[action as keyof typeof actionConfig];
  const Icon = config.icon;

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (action === 'assign_user') {
      if (!assignedUser) {
        newErrors.assignUser = 'Please select a user to assign';
      }
    } else if (action === 'exclude_variance') {
      if (!reason || reason.trim().length === 0) {
        newErrors.reason = 'Please provide a reason for exclusion';
      } else if (reason.trim().length < 10) {
        newErrors.reason = 'Reason must be at least 10 characters';
      }
    } else if (action === 'flag_investigation') {
      if (notes && notes.trim().length > 0 && notes.trim().length < 10) {
        newErrors.notes = 'Note must be at least 10 characters or empty';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleConfirm = () => {
    if (!validateForm()) {
      return;
    }

    const metadata: any = {};

    if (action === 'assign_user' && assignedUser) {
      metadata.assignedUserId = assignedUser;
    }

    if (notes && notes.trim()) {
      metadata.notes = notes.trim();
    }

    if (reason && reason.trim()) {
      metadata.reason = reason.trim();
    }

    onConfirm(metadata);
  };

  const isFormValid = (): boolean => {
    if (action === 'assign_user') {
      return !!assignedUser;
    } else if (action === 'exclude_variance') {
      return !!reason && reason.trim().length >= 10;
    } else if (action === 'flag_investigation') {
      if (notes && notes.trim().length > 0 && notes.trim().length < 10) {
        return false;
      }
    }
    return true;
  };

  const totalAmount = selectedTransactions.reduce((sum, t) => sum + t.amount_cents / 100, 0);

  return (
    <Dialog open={true} onOpenChange={(open) => { if (!open) onCancel(); }}>
      <DialogContent className="max-w-2xl" data-testid="modal-bulk-action">
        <DialogHeader>
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-md ${config.bgColor}`}>
              <Icon className={`w-6 h-6 ${config.iconColor}`} />
            </div>
            <DialogTitle className="text-xl" data-testid="text-modal-title">
              {config.title}
            </DialogTitle>
          </div>
          <DialogDescription data-testid="text-modal-description">
            {config.description}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Transaction Summary */}
          <div className="bg-muted/30 border border-border rounded-md p-4">
            <h3 className="text-sm font-semibold text-foreground mb-3">
              Selection Summary
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Transactions:</span>
                <span className="ml-2 font-semibold text-foreground" data-testid="text-summary-count">{selectedCount}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Total Amount:</span>
                <span className="ml-2 font-semibold text-foreground" data-testid="text-summary-amount">
                  ${totalAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Platforms:</span>
                <span className="ml-2 font-semibold text-foreground" data-testid="text-summary-platforms">
                  {[...new Set(selectedTransactions.map(t => t.platform_name))].join(', ')}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Date Range:</span>
                <span className="ml-2 font-semibold text-foreground" data-testid="text-summary-date-range">
                  {new Date(Math.min(...selectedTransactions.map(t => new Date(t.timestamp).getTime()))).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  {' - '}
                  {new Date(Math.max(...selectedTransactions.map(t => new Date(t.timestamp).getTime()))).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </span>
              </div>
            </div>
          </div>

          {/* Conditional Input Fields */}
          {action === 'assign_user' && (
            <div>
              <Label htmlFor="assigned-user" className="mb-2">
                Assign to Team Member <span className="text-destructive">*</span>
              </Label>
              {/* Native <select> retained: D1 Select (Radix) provides a fully custom dropdown
                  with fundamentally different UX from native OS <select>. Native is preferred
                  here for platform-consistent UX. Exception-tagged in D2_SCOPE.md. */}
              <select
                id="assigned-user"
                value={assignedUser}
                onChange={(e) => {
                  setAssignedUser(e.target.value);
                  setErrors(prev => ({ ...prev, assignUser: '' }));
                }}
                className={`mt-2 flex h-9 w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background
                           focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2
                           ${errors.assignUser ? 'border-destructive' : 'border-input'}`}
                data-testid="select-assign-user"
              >
                <option value="">Select team member...</option>
                <option value="user1">John Smith (Finance)</option>
                <option value="user2">Sarah Johnson (Accounting)</option>
                <option value="user3">Mike Chen (Operations)</option>
              </select>
              {errors.assignUser && (
                <p className="mt-1 text-sm text-destructive" data-testid="error-assign-user">
                  {errors.assignUser}
                </p>
              )}
            </div>
          )}

          {(action === 'flag_investigation' || action === 'exclude_variance') && (
            <div>
              <Label htmlFor="reason" className="mb-2">
                Reason {action === 'exclude_variance' && <span className="text-destructive">*</span>}
              </Label>
              <Input
                id="reason"
                type="text"
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                  setErrors(prev => ({ ...prev, reason: '' }));
                }}
                placeholder="e.g., Legacy data from migration, Known refund processing delay"
                className={`mt-2 ${errors.reason ? 'border-destructive' : ''}`}
                required={action === 'exclude_variance'}
                data-testid="input-reason"
              />
              {errors.reason && (
                <p className="mt-1 text-sm text-destructive" data-testid="error-reason">
                  {errors.reason}
                </p>
              )}
            </div>
          )}

          {/* Notes (all actions) */}
          <div>
            <Label htmlFor="notes" className="mb-2">Notes (Optional)</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                setErrors(prev => ({ ...prev, notes: '' }));
              }}
              rows={3}
              placeholder="Add any additional context or notes..."
              className={`mt-2 resize-none ${errors.notes ? 'border-destructive' : ''}`}
              data-testid="textarea-notes"
            />
            {errors.notes && (
              <p className="mt-1 text-sm text-destructive" data-testid="error-notes">
                {errors.notes}
              </p>
            )}
          </div>

          {/* Warning Message */}
          <Alert className="bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-900">
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-500" />
            <AlertDescription className="text-amber-800 dark:text-amber-200" data-testid="text-warning-message">
              {config.warningText}
            </AlertDescription>
          </Alert>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onCancel}
            data-testid="button-cancel-action"
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!isFormValid()}
            className={`text-white ${config.confirmColor}`}
            data-testid="button-confirm-action"
          >
            {config.confirmButton}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
