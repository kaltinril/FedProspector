import { EmptyState } from '@/components/shared/EmptyState';
import HistoryIcon from '@mui/icons-material/History';

export function OrgActivityLogTab() {
  return (
    <EmptyState
      title="Activity log coming soon"
      message="Organization activity logging is not yet available. Check back in a future release."
      icon={<HistoryIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />}
    />
  );
}
