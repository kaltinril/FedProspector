import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Skeleton from '@mui/material/Skeleton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import PeopleOutlineIcon from '@mui/icons-material/PeopleOutline';

import { useProspectCompetitorSummary } from '@/queries/useInsights';
import { formatCurrency } from '@/utils/formatters';

function competitionLevel(count: number): {
  label: string;
  color: 'success' | 'warning' | 'error';
} {
  if (count <= 3) return { label: 'Low', color: 'success' };
  if (count <= 8) return { label: 'Medium', color: 'warning' };
  return { label: 'High', color: 'error' };
}

interface ProspectCompetitorCardProps {
  prospectId: number;
}

export function ProspectCompetitorCard({ prospectId }: ProspectCompetitorCardProps) {
  const { data, isLoading, isError } = useProspectCompetitorSummary(prospectId);

  if (isLoading) {
    return <Skeleton variant="rounded" width={200} height={32} />;
  }

  if (isError || !data) {
    return null;
  }

  const level = competitionLevel(data.estimatedCompetitorCount);

  return (
    <Tooltip
      title={
        <Box>
          {data.likelyIncumbent && (
            <Typography variant="caption" display="block">
              Incumbent: {data.likelyIncumbent}
            </Typography>
          )}
          {data.incumbentContractValue != null && (
            <Typography variant="caption" display="block">
              Contract value: {formatCurrency(data.incumbentContractValue, true)}
            </Typography>
          )}
          {data.incumbentContractEnd && (
            <Typography variant="caption" display="block">
              Contract ends: {data.incumbentContractEnd}
            </Typography>
          )}
          <Typography variant="caption" display="block">
            Est. competitors: {data.estimatedCompetitorCount}
          </Typography>
        </Box>
      }
      placement="top"
    >
      <Box
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.75,
        }}
      >
        {data.likelyIncumbent && (
          <Chip
            label={data.likelyIncumbent}
            size="small"
            variant="outlined"
            sx={{ maxWidth: 140, fontSize: '0.75rem' }}
          />
        )}
        <Chip
          icon={<PeopleOutlineIcon sx={{ fontSize: '1rem !important' }} />}
          label={`${data.estimatedCompetitorCount} ${level.label}`}
          size="small"
          color={level.color}
          variant="outlined"
          sx={{ fontSize: '0.75rem' }}
        />
      </Box>
    </Tooltip>
  );
}
