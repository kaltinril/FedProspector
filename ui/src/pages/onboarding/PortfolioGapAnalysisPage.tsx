import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import type { GridColDef } from '@mui/x-data-grid';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { DataTable } from '@/components/shared/DataTable';
import { usePortfolioGaps } from '@/queries/useOnboarding';
import type { PortfolioGapDto } from '@/types/onboarding';

type GapType = 'NO_EXPERIENCE' | 'STRONG_MATCH' | 'LOW_OPPORTUNITY' | 'NO_DATA';

const GAP_CONFIG: Record<GapType, { label: string; color: 'error' | 'success' | 'warning' | 'default'; description: string }> = {
  NO_EXPERIENCE: {
    label: 'No Experience',
    color: 'error',
    description: 'Active opportunities in NAICS codes where you have no past performance. These are gaps to fill.',
  },
  STRONG_MATCH: {
    label: 'Strong Match',
    color: 'success',
    description: 'NAICS codes with both active opportunities and past performance. These are your strengths.',
  },
  LOW_OPPORTUNITY: {
    label: 'Low Opportunity',
    color: 'warning',
    description: 'NAICS codes with past performance but few active opportunities. Niche areas.',
  },
  NO_DATA: {
    label: 'No Data',
    color: 'default',
    description: 'NAICS codes with neither active opportunities nor past performance records.',
  },
};

function gapChipColor(gapType: string): 'error' | 'success' | 'warning' | 'default' {
  return GAP_CONFIG[gapType as GapType]?.color ?? 'default';
}

function gapLabel(gapType: string): string {
  return GAP_CONFIG[gapType as GapType]?.label ?? gapType;
}

const columns: GridColDef[] = [
  {
    field: 'naicsCode',
    headerName: 'NAICS Code',
    width: 130,
  },
  {
    field: 'opportunityCount',
    headerName: 'Opportunities',
    width: 130,
    align: 'right',
    headerAlign: 'right',
  },
  {
    field: 'pastPerformanceCount',
    headerName: 'Past Performance',
    width: 150,
    align: 'right',
    headerAlign: 'right',
  },
  {
    field: 'gapType',
    headerName: 'Gap Type',
    width: 160,
    renderCell: (params) => {
      const type = params.value as string;
      return (
        <Chip
          label={gapLabel(type)}
          size="small"
          color={gapChipColor(type)}
        />
      );
    },
  },
];

export default function PortfolioGapAnalysisPage() {
  const { data: gaps, isLoading, isError, refetch } = usePortfolioGaps();

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  if (!gaps || gaps.length === 0) {
    return (
      <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
        <PageHeader
          title="Portfolio Gap Analysis"
          subtitle="Identify gaps between your past performance and available opportunities"
        />
        <EmptyState
          title="No Gap Data"
          message="Add NAICS codes and past performance records to generate gap analysis."
        />
      </Box>
    );
  }

  const noExperience = gaps.filter((g) => g.gapType === 'NO_EXPERIENCE');
  const strongMatch = gaps.filter((g) => g.gapType === 'STRONG_MATCH');
  const lowOpportunity = gaps.filter((g) => g.gapType === 'LOW_OPPORTUNITY');

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Portfolio Gap Analysis"
        subtitle={`${gaps.length} NAICS code${gaps.length !== 1 ? 's' : ''} analyzed`}
      />

      {/* Summary cards */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <SummaryCard type="NO_EXPERIENCE" count={noExperience.length} />
        <SummaryCard type="STRONG_MATCH" count={strongMatch.length} />
        <SummaryCard type="LOW_OPPORTUNITY" count={lowOpportunity.length} />
      </Box>

      {noExperience.length > 0 && (
        <GapSection
          title="Gaps to Fill"
          gapType="NO_EXPERIENCE"
          rows={noExperience}
        />
      )}

      {strongMatch.length > 0 && (
        <GapSection
          title="Strengths"
          gapType="STRONG_MATCH"
          rows={strongMatch}
        />
      )}

      {lowOpportunity.length > 0 && (
        <GapSection
          title="Niche Areas"
          gapType="LOW_OPPORTUNITY"
          rows={lowOpportunity}
        />
      )}
    </Box>
  );
}

function SummaryCard({ type, count }: { type: GapType; count: number }) {
  const config = GAP_CONFIG[type];
  return (
    <Card sx={{ minWidth: 200, flex: 1, borderTop: 3, borderColor: `${config.color}.main` }}>
      <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
        <Typography variant="h4" color={`${config.color}.main`}>
          {count}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {config.label}
        </Typography>
      </CardContent>
    </Card>
  );
}

function GapSection({
  title,
  gapType,
  rows,
}: {
  title: string;
  gapType: GapType;
  rows: PortfolioGapDto[];
}) {
  const config = GAP_CONFIG[gapType];
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" sx={{ mb: 0.5 }}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {config.description}
      </Typography>
      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(row: PortfolioGapDto) => `${row.naicsCode}-${row.gapType}`}
        sortModel={[{ field: 'opportunityCount', sort: 'desc' }]}
      />
    </Box>
  );
}
