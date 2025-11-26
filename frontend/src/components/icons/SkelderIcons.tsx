/**
 * Skeldir Custom Icon Library
 * 
 * Brand-specific SVG icons designed to establish Skeldir identity
 * and improve cognitive clarity across the dashboard interface.
 * 
 * All icons follow accessibility best practices with aria-label support.
 */

/**
 * Base icon props interface
 * All custom Skeldir icons extend this interface
 */
export interface BaseIconProps {
  size?: number;
  className?: string;
  'aria-label'?: string;
}

/**
 * ==============================================
 * PRIMARY ICONS - High Visibility Components
 * ==============================================
 */

/**
 * Data Integrity Seal Icon
 * Usage: DataConfidenceBar, ReconciliationStatus severity indicators
 * Replaces: Generic Shield icon from Lucide
 */
export interface DataIntegritySealProps extends BaseIconProps {
  confidence: 'high' | 'medium' | 'low';
}

export const DataIntegritySeal: React.FC<DataIntegritySealProps> = ({
  size = 24,
  className = '',
  confidence,
  'aria-label': ariaLabel,
}) => {
  const colorMap = {
    high: '#10B981',
    medium: '#F59E0B',
    low: '#EF4444',
  };

  const fill = colorMap[confidence];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
    >
      {/* Outer shield border */}
      <path
        d="M12 2.5L4 6v6c0 5.52 3.82 10.69 8 12 4.18-1.31 8-6.48 8-12V6l-8-3.5z"
        stroke={fill}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      
      {/* Inner scanning rings (decorative) */}
      <circle
        cx="12"
        cy="11"
        r="4"
        stroke={fill}
        strokeWidth="1"
        opacity="0.3"
        fill="none"
      />
      <circle
        cx="12"
        cy="11"
        r="6.5"
        stroke={fill}
        strokeWidth="0.8"
        opacity="0.2"
        fill="none"
      />

      {/* Status indicator overlay */}
      {confidence === 'high' && (
        <path
          d="M9 11.5l2 2 4-4"
          stroke={fill}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
      
      {confidence === 'medium' && (
        <path
          d="M12 8v4m0 3h.01"
          stroke={fill}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
      
      {confidence === 'low' && (
        <path
          d="M10 10l4 4m0-4l-4 4"
          stroke={fill}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
};

/**
 * Verification Checkmark Badge Icon
 * Usage: Verified Revenue card, platform status indicators
 * Replaces: Standard CheckCircle icon from Lucide
 */
export const VerificationCheckmarkBadge: React.FC<BaseIconProps> = ({
  size = 24,
  className = '',
  'aria-label': ariaLabel,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
    >
      {/* Circular badge with gradient effect */}
      <defs>
        <linearGradient id="verifiedGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#10B981" />
          <stop offset="100%" stopColor="#059669" />
        </linearGradient>
      </defs>
      
      {/* Outer glow ring */}
      <circle 
        cx="12" 
        cy="12" 
        r="11" 
        fill="#10B981" 
        opacity="0.15"
      />
      
      {/* Main badge circle */}
      <circle 
        cx="12" 
        cy="12" 
        r="9.5" 
        fill="url(#verifiedGradient)"
      />
      
      {/* White checkmark */}
      <path
        d="M8 12l2.5 2.5L16 9"
        stroke="#FFFFFF"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

/**
 * Pending Verification Indicator Icon
 * Usage: Unverified Revenue card, processing states
 * Replaces: AlertCircle or HelpCircle icon from Lucide
 */
export const PendingVerificationIndicator: React.FC<BaseIconProps> = ({
  size = 24,
  className = '',
  'aria-label': ariaLabel,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
    >
      {/* Full circle outline */}
      <circle 
        cx="12" 
        cy="12" 
        r="10" 
        stroke="#F59E0B" 
        strokeWidth="2"
        fill="none"
      />
      
      {/* Half-filled indicator (180deg arc) */}
      <path
        d="M12 2 A 10 10 0 0 1 22 12 A 10 10 0 0 1 12 22 L 12 2"
        fill="#F59E0B"
        opacity="0.25"
      />
      
      {/* Clock/timer visualization */}
      <g transform="translate(12, 12)">
        {/* Clock center dot */}
        <circle cx="0" cy="0" r="1.5" fill="#F59E0B" />
        
        {/* Hour hand (pointing up) */}
        <path
          d="M0 0 L0 -4"
          stroke="#F59E0B"
          strokeWidth="2"
          strokeLinecap="round"
        />
        
        {/* Minute hand (pointing right) */}
        <path
          d="M0 0 L3.5 0"
          stroke="#F59E0B"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
};

/**
 * ==============================================
 * SECONDARY ICONS - Supporting Components
 * ==============================================
 */

/**
 * Platform Connection Icon
 * Usage: Empty state CTAs, connection prompts
 * Replaces: Link icon from Lucide
 */
export const PlatformConnectionIcon: React.FC<BaseIconProps> = ({
  size = 24,
  className = '',
  'aria-label': ariaLabel,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
    >
      {/* Platform node 1 (left) */}
      <rect
        x="2"
        y="8"
        width="7"
        height="8"
        rx="2"
        stroke="#3B82F6"
        strokeWidth="1.5"
        fill="none"
      />
      
      {/* Platform node 2 (right) */}
      <rect
        x="15"
        y="8"
        width="7"
        height="8"
        rx="2"
        stroke="#3B82F6"
        strokeWidth="1.5"
        fill="none"
      />
      
      {/* Connection line with data flow indicators */}
      <path
        d="M9 12 L15 12"
        stroke="#3B82F6"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      
      {/* Bidirectional arrows */}
      <path
        d="M11 10 L9 12 L11 14"
        stroke="#3B82F6"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M13 10 L15 12 L13 14"
        stroke="#3B82F6"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

/**
 * Trend Indicator Icons
 * Usage: DataConfidenceBar trend visualization
 * Replaces: TrendingUp/TrendingDown/Minus icons from Lucide
 */
export interface TrendIconProps extends BaseIconProps {
  direction: 'up' | 'down' | 'stable';
}

export const TrendIndicator: React.FC<TrendIconProps> = ({
  size = 24,
  className = '',
  direction,
  'aria-label': ariaLabel,
}) => {
  const colorMap = {
    up: '#10B981',
    down: '#EF4444',
    stable: '#6B7280',
  };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
    >
      {direction === 'up' && (
        <>
          <path
            d="M3 17l6-6 4 4 8-8"
            stroke={colorMap.up}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M17 7h4v4"
            stroke={colorMap.up}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
      
      {direction === 'down' && (
        <>
          <path
            d="M3 7l6 6 4-4 8 8"
            stroke={colorMap.down}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M17 17h4v-4"
            stroke={colorMap.down}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
      
      {direction === 'stable' && (
        <path
          d="M5 12h14"
          stroke={colorMap.stable}
          strokeWidth="2"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
};

/**
 * Reconciliation Status Icons
 * Usage: Platform card status indicators, transaction status badges
 * Replaces: Loader, CheckCircle, XCircle icons from Lucide
 */
export interface ReconciliationStatusIconProps extends BaseIconProps {
  status: 'processing' | 'complete' | 'failed' | 'pending';
}

export const ReconciliationStatusIcon: React.FC<ReconciliationStatusIconProps> = ({
  size = 24,
  className = '',
  status,
  'aria-label': ariaLabel,
}) => {
  const colorMap = {
    processing: '#3B82F6',
    complete: '#10B981',
    failed: '#EF4444',
    pending: '#F59E0B',
  };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
    >
      {/* Processing: animated spinner */}
      {status === 'processing' && (
        <>
          <circle
            cx="12"
            cy="12"
            r="9"
            stroke={colorMap.processing}
            strokeWidth="2"
            opacity="0.25"
          />
          <path
            d="M21 12a9 9 0 01-9 9"
            stroke={colorMap.processing}
            strokeWidth="2"
            strokeLinecap="round"
            className="animate-spin"
            style={{ transformOrigin: '12px 12px' }}
          />
        </>
      )}
      
      {/* Complete: checkmark in circle */}
      {status === 'complete' && (
        <>
          <circle
            cx="12"
            cy="12"
            r="9"
            fill={colorMap.complete}
            opacity="0.15"
          />
          <circle
            cx="12"
            cy="12"
            r="9"
            stroke={colorMap.complete}
            strokeWidth="2"
          />
          <path
            d="M8 12l2 2 4-4"
            stroke={colorMap.complete}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
      
      {/* Failed: X in circle */}
      {status === 'failed' && (
        <>
          <circle
            cx="12"
            cy="12"
            r="9"
            fill={colorMap.failed}
            opacity="0.15"
          />
          <circle
            cx="12"
            cy="12"
            r="9"
            stroke={colorMap.failed}
            strokeWidth="2"
          />
          <path
            d="M10 10l4 4m0-4l-4 4"
            stroke={colorMap.failed}
            strokeWidth="2"
            strokeLinecap="round"
          />
        </>
      )}
      
      {/* Pending: clock in circle */}
      {status === 'pending' && (
        <>
          <circle
            cx="12"
            cy="12"
            r="9"
            stroke={colorMap.pending}
            strokeWidth="2"
          />
          <path
            d="M12 7v5l3 3"
            stroke={colorMap.pending}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
    </svg>
  );
};

/**
 * Export Icon
 * Usage: Export buttons, data download actions
 * Replaces: Download icon from Lucide
 */
export const ExportIcon: React.FC<BaseIconProps> = ({
  size = 24,
  className = '',
  'aria-label': ariaLabel,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
    >
      {/* Document outline */}
      <path
        d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"
        stroke="#3B82F6"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      
      {/* Folded corner */}
      <path
        d="M14 2v6h6"
        stroke="#3B82F6"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      
      {/* Arrow pointing down/out */}
      <path
        d="M12 13v6m0 0l-3-3m3 3l3-3"
        stroke="#3B82F6"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

/**
 * Investigation Icon
 * Usage: "Investigate" buttons in reconciliation discrepancy panels
 * Replaces: Search or Eye icon from Lucide
 */
export const InvestigationIcon: React.FC<BaseIconProps> = ({
  size = 24,
  className = '',
  'aria-label': ariaLabel,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
    >
      {/* Magnifying glass circle */}
      <circle
        cx="11"
        cy="11"
        r="7"
        stroke="#3B82F6"
        strokeWidth="2"
      />
      
      {/* Magnifying glass handle */}
      <path
        d="M16 16l4.5 4.5"
        stroke="#3B82F6"
        strokeWidth="2"
        strokeLinecap="round"
      />
      
      {/* Document lines inside glass */}
      <path
        d="M9 10h4M9 12h2"
        stroke="#3B82F6"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.5"
      />
    </svg>
  );
};
