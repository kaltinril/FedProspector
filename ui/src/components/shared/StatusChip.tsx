import Chip from '@mui/material/Chip';

interface StatusChipProps {
  status: string;
  size?: 'small' | 'medium';
}

type ChipColor = 'success' | 'default' | 'warning' | 'error' | 'info' | 'primary';

const STATUS_COLOR_MAP: Record<string, ChipColor> = {
  active: 'success',
  open: 'success',
  published: 'success',
  awarded: 'success',
  won: 'success',
  closed: 'default',
  archived: 'default',
  inactive: 'default',
  draft: 'warning',
  pending: 'warning',
  qualifying: 'warning',
  lead: 'warning',
  cancelled: 'error',
  rejected: 'error',
  lost: 'error',
  expired: 'error',
  'not awarded': 'error',
  'no-bid': 'error',
  review: 'info',
  'in review': 'info',
  'in progress': 'info',
  pursuing: 'info',
  proposal: 'info',
  submitted: 'primary',
};

function getChipColor(status: string): ChipColor {
  return STATUS_COLOR_MAP[status.toLowerCase()] ?? 'default';
}

export function StatusChip({ status, size = 'small' }: StatusChipProps) {
  return (
    <Chip
      label={status}
      size={size}
      color={getChipColor(status)}
      variant="filled"
    />
  );
}
