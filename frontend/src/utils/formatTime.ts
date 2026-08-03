/**
 * Robust Time & Date Formatter Utility
 * Handles ISO strings, Date objects, Unix timestamps, and timezone skews.
 */

export function formatDateTime(dateInput?: string | Date | number | null): string {
  if (!dateInput) return 'N/A';
  try {
    const d = new Date(dateInput);
    if (isNaN(d.getTime())) return String(dateInput);

    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(dateInput);
  }
}

export function formatTimeOnly(dateInput?: string | Date | number | null): string {
  if (!dateInput) return 'N/A';
  try {
    const d = new Date(dateInput);
    if (isNaN(d.getTime())) return String(dateInput);
    return d.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(dateInput);
  }
}

export function formatRelativeTime(dateInput?: string | Date | number | null): string {
  if (!dateInput) return 'Just now';
  try {
    let d: Date;
    if (typeof dateInput === 'string' && !dateInput.includes('Z') && !dateInput.includes('+')) {
      // Append Z to ISO string if missing timezone to force UTC parsing
      d = new Date(dateInput.replace(' ', 'T') + 'Z');
    } else {
      d = new Date(dateInput);
    }

    if (isNaN(d.getTime())) return String(dateInput);

    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    
    if (diffMs < 0 || diffMs < 60000) return 'Just now'; // If under 1 minute or future skew
    
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);

    if (diffMins < 60) return `${diffMins} mins ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;

    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return String(dateInput);
  }
}

export function formatDateOnly(dateInput?: string | Date | number | null): string {
  if (!dateInput) return 'N/A';
  try {
    const d = new Date(dateInput);
    if (isNaN(d.getTime())) return String(dateInput);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  } catch {
    return String(dateInput);
  }
}
