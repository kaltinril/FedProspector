import { format, formatDistanceToNow, differenceInDays } from 'date-fns';

function toDate(date: string | Date | null | undefined): Date | null {
  if (date == null) return null;
  const d = typeof date === 'string' ? new Date(date) : date;
  return isNaN(d.getTime()) ? null : d;
}

/** Format as "Mar 5, 2026" */
export function formatDate(date: string | Date | null | undefined): string {
  const d = toDate(date);
  if (!d) return '--';
  return format(d, 'MMM d, yyyy');
}

/** Format as "Mar 5, 2026, 3:45 PM" */
export function formatDateTime(date: string | Date | null | undefined): string {
  const d = toDate(date);
  if (!d) return '--';
  return format(d, 'MMM d, yyyy, h:mm a');
}

/** Format as "3 days ago" */
export function formatRelative(date: string | Date | null | undefined): string {
  const d = toDate(date);
  if (!d) return '--';
  return formatDistanceToNow(d, { addSuffix: true });
}

/** Format as "5 days left" or "Expired" */
export function formatCountdown(date: string | Date | null | undefined): string {
  const d = toDate(date);
  if (!d) return '--';
  const days = differenceInDays(d, new Date());
  if (days < 0) return 'Expired';
  if (days === 0) return 'Today';
  if (days === 1) return '1 day left';
  return `${days} days left`;
}
