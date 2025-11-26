import { useState } from 'react';
import { X, AlertTriangle, CheckCircle, Flag, Archive, UserPlus } from 'lucide-react';
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

  // Check if form is valid for enabling/disabling confirm button
  const isFormValid = (): boolean => {
    if (action === 'assign_user') {
      return !!assignedUser;
    } else if (action === 'exclude_variance') {
      return !!reason && reason.trim().length >= 10;
    } else if (action === 'flag_investigation') {
      // Notes are optional, but if provided, must be at least 10 characters
      if (notes && notes.trim().length > 0 && notes.trim().length < 10) {
        return false;
      }
    }
    // mark_reviewed doesn't have required fields
    return true;
  };

  // Calculate total amount
  const totalAmount = selectedTransactions.reduce((sum, t) => sum + t.amount, 0);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" data-testid="modal-bulk-action">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 dark:bg-black/70 transition-opacity"
        onClick={onCancel}
        data-testid="backdrop-bulk-action-modal"
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-card border border-border rounded-md shadow-xl w-full max-w-2xl transform transition-all">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-border">
            <div className="flex items-center space-x-3">
              <div className={`p-2 rounded-md ${config.bgColor}`}>
                <Icon className={`w-6 h-6 ${config.iconColor}`} />
              </div>
              <h2 className="text-xl font-bold text-foreground" data-testid="text-modal-title">{config.title}</h2>
            </div>
            <button
              onClick={onCancel}
              className="text-muted-foreground hover:text-foreground transition-colors"
              data-testid="button-close-modal"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Body */}
          <div className="p-6 space-y-6">
            {/* Description */}
            <p className="text-foreground/80" data-testid="text-modal-description">{config.description}</p>

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
                    {[...new Set(selectedTransactions.map(t => t.platform))].join(', ')}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Date Range:</span>
                  <span className="ml-2 font-semibold text-foreground" data-testid="text-summary-date-range">
                    {new Date(Math.min(...selectedTransactions.map(t => new Date(t.date).getTime()))).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    {' - '}
                    {new Date(Math.max(...selectedTransactions.map(t => new Date(t.date).getTime()))).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                </div>
              </div>
            </div>

            {/* Conditional Input Fields */}
            {action === 'assign_user' && (
              <div>
                <label htmlFor="assigned-user" className="block text-sm font-medium text-foreground mb-2">
                  Assign to Team Member <span className="text-red-600 dark:text-red-500">*</span>
                </label>
                <select
                  id="assigned-user"
                  value={assignedUser}
                  onChange={(e) => {
                    setAssignedUser(e.target.value);
                    setErrors(prev => ({ ...prev, assignUser: '' }));
                  }}
                  className={`w-full px-3 py-2 bg-background border rounded-md text-foreground 
                             focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-600
                             ${errors.assignUser ? 'border-red-500 dark:border-red-600' : 'border-border'}`}
                  data-testid="select-assign-user"
                >
                  <option value="">Select team member...</option>
                  <option value="user1">John Smith (Finance)</option>
                  <option value="user2">Sarah Johnson (Accounting)</option>
                  <option value="user3">Mike Chen (Operations)</option>
                </select>
                {errors.assignUser && (
                  <p className="mt-1 text-sm text-red-600 dark:text-red-500" data-testid="error-assign-user">
                    {errors.assignUser}
                  </p>
                )}
              </div>
            )}

            {(action === 'flag_investigation' || action === 'exclude_variance') && (
              <div>
                <label htmlFor="reason" className="block text-sm font-medium text-foreground mb-2">
                  Reason {action === 'exclude_variance' && <span className="text-red-600 dark:text-red-500">*</span>}
                </label>
                <input
                  id="reason"
                  type="text"
                  value={reason}
                  onChange={(e) => {
                    setReason(e.target.value);
                    setErrors(prev => ({ ...prev, reason: '' }));
                  }}
                  placeholder="e.g., Legacy data from migration, Known refund processing delay"
                  className={`w-full px-3 py-2 bg-background border rounded-md text-foreground 
                             focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-600
                             ${errors.reason ? 'border-red-500 dark:border-red-600' : 'border-border'}`}
                  required={action === 'exclude_variance'}
                  data-testid="input-reason"
                />
                {errors.reason && (
                  <p className="mt-1 text-sm text-red-600 dark:text-red-500" data-testid="error-reason">
                    {errors.reason}
                  </p>
                )}
              </div>
            )}

            {/* Notes (all actions) */}
            <div>
              <label htmlFor="notes" className="block text-sm font-medium text-foreground mb-2">
                Notes (Optional)
              </label>
              <textarea
                id="notes"
                value={notes}
                onChange={(e) => {
                  setNotes(e.target.value);
                  setErrors(prev => ({ ...prev, notes: '' }));
                }}
                rows={3}
                placeholder="Add any additional context or notes..."
                className={`w-full px-3 py-2 bg-background border rounded-md text-foreground 
                           focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-600 resize-none
                           ${errors.notes ? 'border-red-500 dark:border-red-600' : 'border-border'}`}
                data-testid="textarea-notes"
              />
              {errors.notes && (
                <p className="mt-1 text-sm text-red-600 dark:text-red-500" data-testid="error-notes">
                  {errors.notes}
                </p>
              )}
            </div>

            {/* Warning Message */}
            <div className="flex items-start space-x-3 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-md">
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-amber-800 dark:text-amber-200" data-testid="text-warning-message">{config.warningText}</p>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end space-x-3 p-6 border-t border-border bg-muted/30">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-foreground bg-background border border-border rounded-md hover-elevate active-elevate-2
                         transition-colors focus:outline-none focus:ring-2 focus:ring-foreground/20 focus:ring-offset-2"
              data-testid="button-cancel-action"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={!isFormValid()}
              className={`px-4 py-2 text-white rounded-md transition-colors focus:outline-none focus:ring-2 
                         focus:ring-offset-2 ${config.confirmColor} disabled:opacity-50 disabled:cursor-not-allowed`}
              data-testid="button-confirm-action"
            >
              {config.confirmButton}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
