const INVERSE = 'var(--sk-color-text-inverse)';

type MarkProps = { className?: string };

const MARK_SIZE = 24;

/** Benchmark source transitioning — classic price tag with fold and punch hole. */
export function BenchmarkTransitionMark({ className }: MarkProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      width={MARK_SIZE}
      height={MARK_SIZE}
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M13.707 3.293A.996.996 0 0 0 13 3H4a1 1 0 0 0-1 1v9c0 .266.105.52.293.707l8 8a.997.997 0 0 0 1.414 0l9-9a.999.999 0 0 0 0-1.414l-8-8z"
      />
      <path
        fill="none"
        stroke={INVERSE}
        strokeWidth="1.35"
        strokeLinejoin="round"
        d="M12 19.586l-7-7V5h7.586l7 7L12 19.586z"
      />
      <circle cx="8.496" cy="8.495" r="1.5" fill={INVERSE} />
    </svg>
  );
}
