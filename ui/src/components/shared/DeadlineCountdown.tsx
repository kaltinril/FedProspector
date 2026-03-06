import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { differenceInDays, differenceInHours, format, parseISO } from 'date-fns';

interface DeadlineCountdownProps {
  deadline: string | null;
  showDate?: boolean;
}

type ChipColor = 'success' | 'warning' | 'error' | 'default';

function getCountdownInfo(deadline: string): {
  label: string;
  color: ChipColor;
} {
  const deadlineDate = parseISO(deadline);
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

  const { label, color } = getCountdownInfo(deadline);
  const formattedDate = format(parseISO(deadline), 'MMM d, yyyy');

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
