import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import type { GridColDef } from '@mui/x-data-grid';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { DataTable } from '@/components/shared/DataTable';
import { useCertificationAlerts } from '@/queries/useOnboarding';
import { formatDate } from '@/utils/dateFormatters';
import type { CertificationAlertDto } from '@/types/onboarding';

function alertColor(level: string): 'error' | 'warning' | 'info' | 'default' {
  switch (level.toUpperCase()) {
    case 'URGENT':
      return 'error';
    case 'WARNING':
      return 'warning';
    case 'NOTICE':
      return 'info';
    default:
      return 'default';
  }
}

const columns: GridColDef[] = [
  {
    field: 'certificationType',
    headerName: 'Certification',
    flex: 2,
    minWidth: 180,
  },
  {
    field: 'expirationDate',
    headerName: 'Expiration Date',
    width: 150,
    renderCell: (params) => (
      <Typography variant="body2">
        {formatDate(params.value as string)}
      </Typography>
    ),
  },
  {
    field: 'daysUntilExpiration',
    headerName: 'Days Until',
    width: 120,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => {
      const days = params.value as number;
      const color = days <= 30 ? 'error' : days <= 90 ? 'warning' : 'default';
      return <Chip label={`${days}d`} size="small" color={color} />;
    },
  },
  {
    field: 'alertLevel',
    headerName: 'Alert Level',
    width: 130,
    renderCell: (params) => {
      const level = params.value as string;
      return (
        <Chip
          label={level}
          size="small"
          color={alertColor(level)}
        />
      );
    },
  },
  {
    field: 'source',
    headerName: 'Source',
    width: 140,
  },
];

export default function CertificationAlertsPage() {
  const { data: alerts, isLoading, isError, refetch } = useCertificationAlerts();

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  if (!alerts || alerts.length === 0) {
    return (
      <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
        <PageHeader
          title="Certification Alerts"
          subtitle="Monitor certification expiration dates"
        />
        <EmptyState
          title="No Certification Alerts"
          message="All certifications are current. No expirations to monitor."
        />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Certification Alerts"
        subtitle={`${alerts.length} certification${alerts.length !== 1 ? 's' : ''} with upcoming expirations`}
      />

      <DataTable
        columns={columns}
        rows={alerts}
        getRowId={(row: CertificationAlertDto) =>
          `${row.certificationType}-${row.expirationDate}`
        }
        sortModel={[{ field: 'daysUntilExpiration', sort: 'asc' }]}
      />
    </Box>
  );
}
