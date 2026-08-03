import React from 'react';

interface BadgeProps {
  level: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE' | 'BRAND' | string;
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ level, children, className = '' }) => {
  let colorStyle = 'bg-slate-800 text-slate-300 border-slate-700';

  const lUpper = level.toUpperCase();
  if (lUpper === 'HIGH' || lUpper === 'CRITICAL') {
    colorStyle = 'badge-high';
  } else if (lUpper === 'MEDIUM') {
    colorStyle = 'badge-medium';
  } else if (lUpper === 'LOW') {
    colorStyle = 'badge-low';
  } else if (lUpper === 'BRAND' || lUpper === 'ACTIVE' || lUpper === 'APPROVED') {
    colorStyle = 'badge-brand';
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider border ${colorStyle} ${className}`}>
      {children}
    </span>
  );
};
