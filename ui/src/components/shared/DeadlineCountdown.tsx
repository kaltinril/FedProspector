import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { differenceInDays, differenceInHours, format, isValid, parseISO } from 'date-fns';

interface DeadlineCountdownProps {
  deadline: string | null;
  showDate?: boolean;
}

type ChipColor = 'success' | 'warning' | 'error' | 'default';

function getCountdownInfo(deadlineDate: Date): {
  label: string;
  color: ChipColor;
} {
  const now = new Date();
  const daysLeft = differenceInDays(deadlineDate, now);
  const hoursLeft = differenceInHours(deadlineDate, now);

  if (hoursLeft <= 0) {
    return { label: 'Expired', color: 'default' };
  }

  if (daysLeft < 1) {
    return { label: `${hoursLeft}h left`, color: 'error' };
  }

  if (daysLeft < 7) {
    return { label: `${daysLeft}d left`, color: 'error' };
  }

  if (daysLeft <= 14) {
    return { label: `${daysLeft}d left`, color: 'warning' };
  }

  return { label: `${daysLeft}d left`, color: 'success' };
}

export function DeadlineCountdown({
  deadline,
  showDate = true,
}: DeadlineCountdownProps) {
  if (!deadline) {
    return (
      <Typography variant="body2" color="text.secondary">
        --
      </Typography>
    );
  }

  const parsed = parseISO(deadline);
  if (!isValid(parsed)) {
    return (
      <Typography variant="body2" color="text.secondary">
        --
      </Typography>
    );
  }

  const { label, color } = getCountdownInfo(parsed);
  const formattedDate = format(parsed, 'MMM d, yyyy');

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
      <Chip label={label} color={color} size="small" variant="filled" />
      {showDate && (
        <Typography variant="body2" color="text.secondary">
          {formattedDate}
        </Typography>
      )}
    </Box>
  );
}
