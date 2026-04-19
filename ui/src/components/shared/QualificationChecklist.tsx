import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import WarningIcon from '@mui/icons-material/Warning';
import HelpOutlineIcon from '@mui/icons-material/HelpOutlined';

interface QualificationItem {
  name: string;
  category: string;
  status: string;
  detail: string;
  sourceUei?: string | null;
}

interface QualificationChecklistProps {
  checks: QualificationItem[];
  overallStatus: string;
  passCount: number;
  failCount: number;
  warningCount: number;
}

function statusIcon(status: string) {
  switch (status) {
    case 'Pass':
      return <CheckCircleIcon sx={{ color: 'success.main' }} titleAccess="Pass" />;
    case 'Fail':
      return <CancelIcon sx={{ color: 'error.main' }} titleAccess="Fail" />;
    case 'Warning':
      return <WarningIcon sx={{ color: 'warning.main' }} titleAccess="Warning" />;
    default:
      return <HelpOutlineIcon sx={{ color: 'text.disabled' }} titleAccess="Unknown" />;
  }
}

function groupByCategory(
  checks: QualificationItem[],
): Record<string, QualificationItem[]> {
  const groups: Record<string, QualificationItem[]> = {};
  for (const check of checks) {
    const key = check.category || 'Other';
    if (!groups[key]) groups[key] = [];
    groups[key].push(check);
  }
  return groups;
}

export function QualificationChecklist({
  checks,
  overallStatus,
  passCount,
  failCount,
  warningCount,
}: QualificationChecklistProps) {
  const theme = useTheme();

  const overallColor =
    overallStatus === 'Qualified'
      ? theme.palette.success.main
      : overallStatus === 'Partially'
        ? theme.palette.warning.main
        : theme.palette.error.main;

  const groups = groupByCategory(checks);

  return (
    <Box>
      {/* Overall status */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          mb: 2,
        }}
      >
        <Chip
          label={overallStatus}
          sx={{
            backgroundColor: overallColor,
            color: '#fff',
            fontWeight: 600,
            fontSize: '0.875rem',
          }}
        />
        <Typography variant="body2" sx={{
          color: "text.secondary"
        }}>
          <Box
            component="span"
            sx={{ color: 'success.main', fontWeight: 600 }}
          >
            {passCount} Pass
          </Box>
          {' \u00b7 '}
          <Box component="span" sx={{ color: 'error.main', fontWeight: 600 }}>
            {failCount} Fail
          </Box>
          {' \u00b7 '}
          <Box
            component="span"
            sx={{ color: 'warning.main', fontWeight: 600 }}
          >
            {warningCount} Warning
          </Box>
        </Typography>
      </Box>
      {/* Grouped checks */}
      {Object.entries(groups).map(([category, items]) => (
        <Box key={category} sx={{ mb: 2 }}>
          <Typography
            variant="subtitle2"
            sx={{
              color: "text.secondary",
              mb: 0.5,
              textTransform: 'uppercase',
              letterSpacing: 0.5
            }}>
            {category}
          </Typography>
          <List disablePadding>
            {items.map((item, index) => (
              <ListItem key={index} disableGutters sx={{ py: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 36 }}>
                  {statusIcon(item.status)}
                </ListItemIcon>
                <ListItemText
                  primary={item.name}
                  secondary={
                    item.sourceUei
                      ? `${item.detail} (via UEI: ${item.sourceUei})`
                      : item.detail
                  }
                />
              </ListItem>
            ))}
          </List>
        </Box>
      ))}
    </Box>
  );
}
