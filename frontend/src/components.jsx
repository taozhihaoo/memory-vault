import React from "react";
import { Link } from "react-router-dom";
import { parseHighlight } from "./api.js";

// ------------------------------------------------------------------- icons
const ICONS = {
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.6-3.6" /></>,
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.6" /><rect x="14" y="3" width="7" height="7" rx="1.6" /><rect x="3" y="14" width="7" height="7" rx="1.6" /><rect x="14" y="14" width="7" height="7" rx="1.6" /></>,
  graph: <><circle cx="6" cy="6" r="2.2" /><circle cx="18" cy="7" r="2.2" /><circle cx="12" cy="18" r="2.2" /><path d="M7.9 6.7 16 7M7.2 7.8l3.5 8.4M16.9 8.8l-3.7 7.5" /></>,
  timeline: <><path d="M4 20V6" /><path d="M4 20h16" /><rect x="7" y="12" width="3" height="5" rx=".8" /><rect x="12" y="8" width="3" height="9" rx=".8" /><rect x="17" y="14" width="3" height="3" rx=".8" /></>,
  document: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /><path d="M9 12h6M9 16h6" /></>,
  tag: <><path d="M3 12V4h8l10 10-8 8z" /><circle cx="7.5" cy="7.5" r="1.2" /></>,
  sparkles: <><path d="m12 3 1.7 4.6L18 9l-4.3 1.4L12 15l-1.7-4.6L6 9l4.3-1.4z" /><path d="m18 15 .8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8z" /></>,
  shield: <><path d="M12 3 5 6v6c0 4.2 2.9 7.6 7 9 4.1-1.4 7-4.8 7-9V6z" /><path d="m9 12 2 2 4-4" /></>,
  database: <><ellipse cx="12" cy="5.5" rx="8" ry="3" /><path d="M4 5.5v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /><path d="M4 11.5v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>,
  refresh: <><path d="M20 11a8 8 0 1 0-2.3 6.3" /><path d="M20 5v6h-6" /></>,
  arrowRight: <><path d="M4 12h16" /><path d="m14 6 6 6-6 6" /></>,
  arrowLeft: <><path d="M20 12H4" /><path d="m10 18-6-6 6-6" /></>,
  chevron: <><path d="m6 9 6 6 6-6" /></>,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c2.6 2.6 3.9 5.7 3.9 9S14.6 18.4 12 21c-2.6-2.6-3.9-5.7-3.9-9S9.4 5.6 12 3z" /></>,
  link: <><path d="M10 13a4 4 0 0 0 5.7 0l2.3-2.3a4 4 0 0 0-5.7-5.7L11 6.3" /><path d="M14 11a4 4 0 0 0-5.7 0L6 13.3A4 4 0 0 0 11.7 19l1.3-1.3" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
  hash: <><path d="M5 9h14M4 15h14M10 3 8 21M16 3l-2 18" /></>,
  zap: <><path d="M13 3 5 14h6l-1 7 8-11h-6z" /></>,
  check: <><path d="m5 12 4.5 4.5L19 7" /></>,
  alert: <><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.2v.1" /></>,
  folder: <><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
  x: <><path d="M6 6l12 12M18 6 6 18" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.1" /></>,
};

export function Icon({ name, size = 18, className = "", strokeWidth = 1.7, ...rest }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {ICONS[name] || ICONS.info}
    </svg>
  );
}

export function BrandMark({ size = 36 }) {
  return (
    <span className="brand-mark" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
        <defs>
          <linearGradient id="mv-brand" x1="4" y1="4" x2="36" y2="36" gradientUnits="userSpaceOnUse">
            <stop stopColor="#818cf8" />
            <stop offset="0.55" stopColor="#6366f1" />
            <stop offset="1" stopColor="#22d3ee" />
          </linearGradient>
        </defs>
        <rect x="1" y="1" width="38" height="38" rx="12" fill="url(#mv-brand)" opacity="0.16" />
        <rect x="1" y="1" width="38" height="38" rx="12" stroke="url(#mv-brand)" strokeOpacity="0.55" />
        <path d="M11 27V13l9 10 9-10v14" stroke="url(#mv-brand)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="20" cy="10" r="2" fill="#22d3ee" />
      </svg>
    </span>
  );
}

// ------------------------------------------------------------- text rendering
/** Render backend-escaped highlight text without dangerouslySetInnerHTML. */
export function Highlight({ html = "" }) {
  const segments = parseHighlight(html);
  return (
    <>
      {segments.map((segment, i) =>
        segment.mark ? <mark key={i}>{segment.text}</mark> : <React.Fragment key={i}>{segment.text}</React.Fragment>
      )}
    </>
  );
}

// ----------------------------------------------------------------- structure
export function PageHeader({ eyebrow, title, subtitle, action }) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {action && <div className="page-header-action">{action}</div>}
    </header>
  );
}

export function Card({ className = "", children, ...rest }) {
  return <section className={`card ${className}`} {...rest}>{children}</section>;
}

export function CardHeading({ icon, title, action }) {
  return (
    <div className="card-heading">
      <div className="card-heading-title">
        {icon && <span className="card-heading-icon"><Icon name={icon} size={16} /></span>}
        <h2>{title}</h2>
      </div>
      {action}
    </div>
  );
}

export function StatCard({ icon, label, value, tone = "indigo", hint }) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <div className="stat-card-top">
        <span className="stat-icon"><Icon name={icon} size={18} /></span>
        {hint && <span className="stat-hint">{hint}</span>}
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export function TypeBadge({ type }) {
  return <span className="type-badge">{type || "unknown"}</span>;
}

export function Chip({ active = false, tone = "", className = "", children, ...rest }) {
  return (
    <button
      type="button"
      className={`chip ${active ? "active" : ""} ${tone ? `chip-${tone}` : ""} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Segmented({ options, value, onChange, ariaLabel }) {
  return (
    <div className="segmented" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={value === option.value ? "active" : ""}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function EmptyState({ icon = "search", title, body, action }) {
  return (
    <div className="empty-state">
      <div className="empty-illustration">
        <span className="empty-ring" />
        <Icon name={icon} size={30} />
      </div>
      <h3>{title}</h3>
      {body && <p>{body}</p>}
      {action}
    </div>
  );
}

export function LoadingState({ label, cards = 3 }) {
  return (
    <div className="loading-state" aria-live="polite" aria-label={label}>
      <div className="loading-label"><span className="spinner" />{label}</div>
      <div className="skeleton-grid">
        {Array.from({ length: cards }, (_, i) => (
          <div className="skeleton" key={i} style={{ animationDelay: `${i * 90}ms` }} />
        ))}
      </div>
    </div>
  );
}

export function ErrorBox({ message, onRetry, retryLabel }) {
  return (
    <div className="error-box">
      <Icon name="alert" size={18} />
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn ghost" onClick={onRetry}>{retryLabel}</button>
      )}
    </div>
  );
}

export function BackLink({ to = "/", label }) {
  return (
    <Link to={to} className="back-link">
      <Icon name="arrowLeft" size={15} />{label}
    </Link>
  );
}
