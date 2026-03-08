import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

interface PWinGaugeProps {
  score: number;
  category: string;
  size?: 'small' | 'medium' | 'large';
  showCategory?: boolean;
}

const SIZE_MAP = {
  small: { gauge: 60, text: 'caption' as const },
  medium: { gauge: 120, text: 'h6' as const },
  large: { gauge: 180, text: 'h4' as const },
};

function useGaugeColor(category: string) {
  const theme = useTheme();
  switch (category) {
    case 'High':
      return theme.palette.success.main;
    case 'Medium':
      return theme.palette.warning.main;
    case 'Low':
      return theme.palette.error.light;
    case 'VeryLow':
      return theme.palette.error.main;
    default:
      return theme.palette.grey[500];
  }
}

export default function PWinGauge({
  score,
  category,
  size = 'medium',
  showCategory = true,
}: PWinGaugeProps) {
  const theme = useTheme();
  const gaugeColor = useGaugeColor(category);
  const { gauge: gaugeSize, text: textVariant } = SIZE_MAP[size];

  return (
    <Box
      sx={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
        {/* Background track */}
        <CircularProgress
          variant="determinate"
          value={100}
          size={gaugeSize}
          thickness={4}
          sx={{
            color: theme.palette.mode === 'dark' ? 'grey.800' : 'grey.200',
            position: 'absolute',
          }}
        />
        {/* Score ring */}
        <CircularProgress
          variant="determinate"
          value={score}
          size={gaugeSize}
          thickness={4}
          sx={{ color: gaugeColor }}
        />
        {/* Center text */}
        <Box
          sx={{
            position: 'absolute',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            inset: 0,
          }}
        >
          <Typography variant={textVariant} fontWeight={700}>
            {Math.round(score)}%
          </Typography>
        </Box>
      </Box>
      {showCategory && (
        <Chip
          label={category}
          size="small"
          sx={{
            mt: 1,
            backgroundColor: gaugeColor,
            color: '#fff',
          }}
        />
      )}
    </Box>
  );
}
