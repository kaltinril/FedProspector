import Typography from '@mui/material/Typography';
import { formatCurrency } from '@/utils/formatters';

interface CurrencyDisplayProps {
  value: number | null | undefined;
  compact?: boolean;
}

export function CurrencyDisplay({ value, compact = false }: CurrencyDisplayProps) {
  return (
    <Typography component="span" variant="inherit">
      {formatCurrency(value, compact)}
    </Typography>
  );
}
