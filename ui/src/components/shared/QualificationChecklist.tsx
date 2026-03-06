import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import RemoveIcon from '@mui/icons-material/Remove';

interface QualificationItem {
  label: string;
  status: 'pass' | 'fail' | 'unknown' | 'na';
  detail?: string;
}

interface QualificationChecklistProps {
  items: QualificationItem[];
}

const STATUS_ICON_MAP: Record<
  QualificationItem['status'],
  { icon: React.ReactNode }
> = {
  pass: { icon: <CheckCircleIcon sx={{ color: 'success.main' }} titleAccess="Passed" /> },
  fail: { icon: <CancelIcon sx={{ color: 'error.main' }} titleAccess="Failed" /> },
  unknown: { icon: <HelpOutlineIcon sx={{ color: 'text.disabled' }} titleAccess="Unknown" /> },
  na: { icon: <RemoveIcon sx={{ color: 'text.disabled' }} titleAccess="Not applicable" /> },
};

export function QualificationChecklist({
  items,
}: QualificationChecklistProps) {
  return (
    <List disablePadding>
      {items.map((item, index) => (
        <ListItem key={index} disableGutters sx={{ py: 0.5 }}>
          <ListItemIcon sx={{ minWidth: 36 }}>
            {STATUS_ICON_MAP[item.status].icon}
          </ListItemIcon>
          <ListItemText primary={item.label} secondary={item.detail} />
        </ListItem>
      ))}
    </List>
  );
}
