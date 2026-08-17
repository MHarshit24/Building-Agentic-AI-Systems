// Hand-drawn inline SVG icons — no external icon package, no emoji.

export function CheckCircleIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.09l4-5.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function PendingCircleIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.5} className={className} aria-hidden="true">
      <circle cx="10" cy="10" r="7.25" />
    </svg>
  );
}

export function SpinnerIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`} aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function AlertTriangleIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.63-1.516 2.63H3.72c-1.347 0-2.189-1.463-1.515-2.63L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 8a1 1 0 100-2 1 1 0 000 2z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function CloseIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
    </svg>
  );
}

// Hub-and-spoke mark: the header logo, standing in for "orchestrated
// multi-agent system" without spelling it out literally.
export function OrchestrationMark({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="3.2" fill="currentColor" />
      <g stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
        <path d="M12 8.8V4.5" />
        <path d="M15.3 10.2l3.2-2.5" />
        <path d="M15.3 13.8l3.2 2.5" />
        <path d="M12 15.2v4.3" />
        <path d="M8.7 13.8l-3.2 2.5" />
        <path d="M8.7 10.2l-3.2-2.5" />
      </g>
      <circle cx="12" cy="4.5" r="1.6" fill="currentColor" opacity="0.55" />
      <circle cx="18.5" cy="7.7" r="1.6" fill="currentColor" opacity="0.55" />
      <circle cx="18.5" cy="16.3" r="1.6" fill="currentColor" opacity="0.55" />
      <circle cx="12" cy="19.5" r="1.6" fill="currentColor" opacity="0.55" />
      <circle cx="5.5" cy="16.3" r="1.6" fill="currentColor" opacity="0.55" />
      <circle cx="5.5" cy="7.7" r="1.6" fill="currentColor" opacity="0.55" />
    </svg>
  );
}

export function VenueIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M12 21.5s6.5-5.8 6.5-11.2a6.5 6.5 0 10-13 0c0 5.4 6.5 11.2 6.5 11.2z" />
      <circle cx="12" cy="10.2" r="2.3" />
    </svg>
  );
}

export function WalletIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M3 7.2A2.2 2.2 0 015.2 5h11.6A2.2 2.2 0 0119 7.2V8H5.2A2.2 2.2 0 013 5.8" />
      <rect x="3" y="8" width="18" height="11" rx="2.2" />
      <path d="M15.5 13.5h2.3" />
    </svg>
  );
}

export function MegaphoneIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M3 10.5v3a1.5 1.5 0 001.5 1.5H6l1.2 4.6a1 1 0 00.97.74H9a1 1 0 001-1.2L9.2 15H10l8 4V5l-8 4H4.5A1.5 1.5 0 003 10.5z" />
      <path d="M18 9a4 4 0 010 6" />
    </svg>
  );
}

export function CalendarIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
      <path d="M8 3v4M16 3v4M3.5 10h17" />
    </svg>
  );
}

export function ShieldAlertIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M12 3l7.5 3v5.4c0 4.8-3.2 8.2-7.5 9.6-4.3-1.4-7.5-4.8-7.5-9.6V6L12 3z" />
      <path d="M12 8.5v4M12 15.8h.01" />
    </svg>
  );
}

export function SparkleIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 2.5l1.7 5.1a3 3 0 001.9 1.9l5.1 1.7-5.1 1.7a3 3 0 00-1.9 1.9L12 20l-1.7-5.1a3 3 0 00-1.9-1.9L3.3 11.2l5.1-1.7a3 3 0 001.9-1.9L12 2.5z" />
      <path d="M19.5 3l.6 1.7 1.7.6-1.7.6-.6 1.7-.6-1.7L17.2 5.3l1.7-.6L19.5 3z" opacity="0.7" />
    </svg>
  );
}

export function ArrowRightIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M3 10a.75.75 0 01.75-.75h10.638L11.29 6.15a.75.75 0 111.02-1.1l5 4.65a.75.75 0 010 1.1l-5 4.65a.75.75 0 11-1.02-1.1l3.098-3.1H3.75A.75.75 0 013 10z"
        clipRule="evenodd"
      />
    </svg>
  );
}
