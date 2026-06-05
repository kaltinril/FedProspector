import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { differenceInDays, differenceInHours, format, isValid, parseISO } from 'date-fns';

interface DeadlineCountdownProps {
  deadline: string | null;
  showDate?: boolean;
}

export type DeadlineChipColor = 'warning' | 'error' | 'default';

// Shared thresholds (days) so all "days left" call sites color consistently.
// Rule: never use green/success. Neutral (default) when comfortable, amber
// (warning) when getting close, red (error) when urgent or already past.
export const DEADLINE_URGENT_DAYS = 3;
export const DEADLINE_WARNING_DAYS = 14;

/**
 * Map a number of days remaining to a chip color.
 * `null`/`undefined` (unknown) is treated as neutral.
 * Negative days (past) are urgent.
 */
export function deadlineChipColor(daysLeft: number | null | undefined): DeadlineChipColor {
  if (daysLeft == null) return 'default';
  if (daysLeft <= DEADLINE_URGENT_DAYS) return 'error';
  if (daysLeft <= DEADLINE_WARNING_DAYS) return 'warning';
  return 'default';
}

function getCountdownInfo(deadlineDate: Date): {
  label: string;
  color: DeadlineChipColor;
} {
  const now = new Date();
  const daysLeft = differenceInDays(deadlineDate, now);
  const hoursLeft = differenceInHours(deadlineDate, now);

  if (hoursLeft <= 0) {
    return { label: 'Expired', color: 'error' };
  }

  if (daysLeft < 1) {
    return { label: `${hoursLeft}h left`, color: 'error' };
  }

  return { label: `${daysLeft}d left`, color: deadlineChipColor(daysLeft) };
}

export function DeadlineCountdown({
  deadline,
  showDate = true,
}: DeadlineCountdownProps) {
  if (!deadline) {
    return (
      <Typography variant="body2" sx={{
        color: "text.secondary"
      }}>--
              </Typography>
    );
  }

  const parsed = parseISO(deadline);
  if (!isValid(parsed)) {
    return (
      <Typography variant="body2" sx={{
        color: "text.secondary"
      }}>--
              </Typography>
    );
  }

  const { label, color } = getCountdownInfo(parsed);
  const formattedDate = format(parsed, 'MMM d, yyyy');

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
      <Chip label={label} color={color} size="small" variant="filled" />
      {showDate && (
        <Typography variant="body2" sx={{
          color: "text.secondary"
        }}>
          {formattedDate}
        </Typography>
      )}
    </Box>
  );
}
