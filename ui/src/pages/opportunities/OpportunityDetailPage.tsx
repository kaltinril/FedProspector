import { useMemo, useState } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import type { GridColDef } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import SavedSearchIcon from '@mui/icons-material/SavedSearch';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import DescriptionIcon from '@mui/icons-material/Description';
import TableChartIcon from '@mui/icons-material/TableChart';
import ImageIcon from '@mui/icons-material/Image';

import { PageHeader } from '@/components/shared/PageHeader';
import { BackToSearch } from '@/components/shared/BackToSearch';
import { TabbedDetailPage } from '@/components/shared/TabbedDetailPage';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { DeadlineCountdown } from '@/components/shared/DeadlineCountdown';
import { BurnRateChart } from '@/components/shared/BurnRateChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { QualificationChecklist } from '@/components/shared/QualificationChecklist';
import { DataTable } from '@/components/shared/DataTable';
import { StatusChip } from '@/components/shared/StatusChip';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { EmptyState } from '@/components/shared/EmptyState';
import { getOpportunity } from '@/api/opportunities';
import { getBurnRate, getMarketShare } from '@/api/awards';
import { createProspect } from '@/api/prospects';
import { createSavedSearch } from '@/api/savedSearches';
import { queryKeys } from '@/queries/queryKeys';
import { formatDate, formatDateTime } from '@/utils/dateFormatters';
import { formatCurrency } from '@/utils/formatters';
import type { OpportunityDetail, RelatedAwardDto, MarketShareDto, ResourceLinkDto } from '@/types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const US_TERRITORIES = ['PR', 'GU', 'VI', 'AS', 'MP'];
const MILITARY_STATES = ['AA', 'AE', 'AP'];

function getLocationIndicator(
  country: string | null | undefined,
  state: string | null | undefined,
): string {
  if (!country || country === 'USA' || country === 'US') {
    const upperState = state?.toUpperCase();
    if (upperState && MILITARY_STATES.includes(upperState)) {
      return 'Military (OCONUS)';
    }
    if (upperState && US_TERRITORIES.includes(upperState)) {
      return 'US Territory';
    }
    return 'CONUS';
  }
  return 'OCONUS';
}

function buildPlaceOfPerformance(opp: OpportunityDetail): string {
  const parts: string[] = [];
  if (opp.popCity) parts.push(opp.popCity);
  if (opp.popState) parts.push(opp.popState);
  if (opp.popZip) parts.push(opp.popZip);
  if (opp.popCountry && opp.popCountry !== 'USA' && opp.popCountry !== 'US') {
    parts.push(opp.popCountry);
  }
  return parts.length > 0 ? parts.join(', ') : '--';
}

function parseResourceLinks(raw: string | null | undefined): { label: string; url: string }[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.map((item: { label?: string; url?: string } | string) => {
        if (typeof item === 'string') return { label: item, url: item };
        return { label: item.label ?? item.url ?? 'Link', url: item.url ?? '' };
      });
    }
  } catch {
    // If not JSON, treat as comma-separated URLs
    return raw.split(',').map((url) => ({ label: url.trim(), url: url.trim() }));
  }
  return [];
}

/** Return an MUI icon component based on content-type. */
function getFileIcon(contentType: string | null | undefined) {
  if (!contentType) return <InsertDriveFileIcon fontSize="small" color="action" />;
  const ct = contentType.toLowerCase();
  if (ct.includes('pdf')) return <PictureAsPdfIcon fontSize="small" color="error" />;
  if (ct.includes('word') || ct.includes('msword') || ct.includes('officedocument.wordprocessing'))
    return <DescriptionIcon fontSize="small" color="primary" />;
  if (ct.includes('spreadsheet') || ct.includes('excel') || ct.includes('ms-excel'))
    return <TableChartIcon fontSize="small" color="success" />;
  if (ct.includes('image/')) return <ImageIcon fontSize="small" color="info" />;
  return <InsertDriveFileIcon fontSize="small" color="action" />;
}

/** Build the display list of resource links, preferring enriched DTO data. */
function getResourceLinksForDisplay(
  opp: OpportunityDetail,
): { label: string; url: string; contentType: string | null }[] {
  // Prefer structured resourceLinkDetails from API (enriched data)
  if (opp.resourceLinkDetails && opp.resourceLinkDetails.length > 0) {
    return opp.resourceLinkDetails.map((rl: ResourceLinkDto, idx: number) => ({
      label: rl.filename ?? `Attachment ${idx + 1}`,
      url: rl.url,
      contentType: rl.contentType,
    }));
  }
  // Fallback: parse the raw JSON string (old/un-enriched data)
  return parseResourceLinks(opp.resourceLinks).map((rl) => ({
    ...rl,
    contentType: null,
  }));
}

// ---------------------------------------------------------------------------
// Tab: Overview
// ---------------------------------------------------------------------------

function OverviewTab({ opp }: { opp: OpportunityDetail }) {
  const [expanded, setExpanded] = useState(false);
  const description = opp.descriptionUrl ?? '';
  const isLong = description.length > 300;
  const locationIndicator = getLocationIndicator(opp.popCountry, opp.popState);
  const resourceLinks = getResourceLinksForDisplay(opp);

  const facts = useMemo(
    () => [
      { label: 'Type', value: opp.type ?? '--' },
      { label: 'Base Type', value: opp.baseType ?? '--' },
      { label: 'Classification / PSC Code', value: opp.classificationCode ?? '--' },
      {
        label: 'Set-Aside',
        value: [opp.setAsideCode, opp.setAsideDescription, opp.setAsideCategory].filter(Boolean).join(' - ') || '--',
      },
      {
        label: 'NAICS',
        value: opp.naicsCode
          ? opp.naicsDescription
            ? `${opp.naicsCode} — ${opp.naicsDescription}`
            : opp.naicsCode
          : '--',
      },
      {
        label: 'NAICS Sector',
        value: opp.naicsSector ?? '--',
      },
      {
        label: 'Size Standard',
        value: opp.sizeStandard ?? '--',
      },
      {
        label: 'Place of Performance',
        value: `${buildPlaceOfPerformance(opp)} (${locationIndicator})`,
      },
      {
        label: 'Security Clearance',
        value: opp.securityClearanceRequired ?? 'Unknown',
      },
      {
        label: 'Period of Performance',
        value:
          opp.periodOfPerformanceStart || opp.periodOfPerformanceEnd
            ? `${formatDate(opp.periodOfPerformanceStart)} - ${formatDate(opp.periodOfPerformanceEnd)}`
            : '--',
      },
      {
        label: 'First Loaded',
        value: formatDateTime(opp.firstLoadedAt),
      },
      {
        label: 'Last Updated',
        value: formatDateTime(opp.lastLoadedAt),
      },
    ],
    [opp, locationIndicator],
  );

  return (
    <Box>
      {/* Description */}
      {description && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Description
          </Typography>
          <Collapse in={expanded || !isLong} collapsedSize={80}>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {description}
            </Typography>
          </Collapse>
          {isLong && (
            <Button
              size="small"
              onClick={() => setExpanded((prev) => !prev)}
              sx={{ mt: 1 }}
            >
              {expanded ? 'Show less' : 'Show more'}
            </Button>
          )}
        </Paper>
      )}

      {/* Key Facts */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Key Facts
        </Typography>
        <KeyFactsGrid facts={facts} columns={2} />

        {/* SAM.gov link */}
        {opp.link && (
          <Box sx={{ mt: 2 }}>
            <Link
              href={opp.link}
              target="_blank"
              rel="noopener noreferrer"
              sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
            >
              View on SAM.gov <OpenInNewIcon fontSize="small" />
            </Link>
          </Box>
        )}

        {/* Resource links */}
        {resourceLinks.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              Resource Links
            </Typography>
            {resourceLinks.map((rl, idx) => (
              <Link
                key={idx}
                href={rl.url}
                target="_blank"
                rel="noopener noreferrer"
                sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}
              >
                {getFileIcon(rl.contentType)}
                {rl.label}
              </Link>
            ))}
          </Box>
        )}
      </Paper>

      {/* Qualification Checklist */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Qualification Checklist
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
          Automated matching against your organization profile is coming soon. All items shown as
          unknown for now.
        </Typography>
        <QualificationChecklist
          items={[
            { label: 'Set-aside eligibility', status: 'unknown', detail: 'Requires organization profile' },
            { label: 'NAICS code match', status: 'unknown', detail: 'Requires organization profile' },
            { label: 'Size standard compliance', status: 'unknown', detail: 'Requires organization profile' },
            { label: 'Security clearance', status: 'unknown', detail: 'Requires organization profile' },
            { label: 'Past performance', status: 'unknown', detail: 'Requires organization profile' },
            { label: 'Geographic eligibility', status: 'unknown', detail: 'Requires organization profile' },
          ]}
        />
      </Paper>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab: History & Incumbent Intel
// ---------------------------------------------------------------------------

const RELATED_AWARD_COLUMNS: GridColDef<RelatedAwardDto>[] = [
  {
    field: 'contractId',
    headerName: 'Contract ID',
    width: 180,
  },
  {
    field: 'vendorName',
    headerName: 'Vendor',
    flex: 1,
    minWidth: 180,
    valueGetter: (_value, row) => row.vendorName ?? '--',
  },
  {
    field: 'dateSigned',
    headerName: 'Date Signed',
    width: 130,
    valueGetter: (_value, row) => (row.dateSigned ? formatDate(row.dateSigned) : '--'),
  },
  {
    field: 'dollarsObligated',
    headerName: 'Obligated',
    width: 140,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_value, row) => row.dollarsObligated,
    renderCell: (params) => formatCurrency(params.value as number | null),
  },
  {
    field: 'baseAndAllOptions',
    headerName: 'Ceiling',
    width: 140,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_value, row) => row.baseAndAllOptions,
    renderCell: (params) => formatCurrency(params.value as number | null),
  },
  {
    field: 'typeOfContract',
    headerName: 'Type',
    width: 100,
    valueGetter: (_value, row) => row.typeOfContract ?? '--',
  },
  {
    field: 'numberOfOffers',
    headerName: 'Offers',
    width: 80,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_value, row) => row.numberOfOffers ?? '--',
  },
];

function HistoryTab({ opp }: { opp: OpportunityDetail }) {
  const navigate = useNavigate();
  const isRecompete = !!(opp.awardeeUei || opp.awardNumber);
  const incumbentUei = opp.incumbentUei ?? opp.awardeeUei;
  const incumbentName = opp.incumbentName ?? opp.awardeeName;

  const firstAward = opp.relatedAwards?.[0];
  const { data: burnRateData } = useQuery({
    queryKey: queryKeys.awards.burnRate(firstAward?.contractId ?? ''),
    queryFn: () => getBurnRate(firstAward!.contractId),
    staleTime: 5 * 60 * 1000,
    enabled: isRecompete && !!firstAward?.contractId,
  });

  if (!isRecompete) {
    return (
      <EmptyState
        title="New Solicitation"
        message="No incumbent information available for this opportunity."
        icon={<InfoOutlinedIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />}
      />
    );
  }

  const incumbentFacts = [
    { label: 'Re-compete Status', value: 'Re-compete' },
    {
      label: 'Incumbent',
      value: incumbentUei ? (
        <Link
          component={RouterLink}
          to={`/entities/${encodeURIComponent(incumbentUei)}`}
        >
          {incumbentName ?? incumbentUei}
        </Link>
      ) : (
        incumbentName ?? '--'
      ),
    },
    { label: 'Incumbent UEI', value: incumbentUei ?? '--' },
    { label: 'Award Number', value: opp.awardNumber ?? '--' },
    { label: 'Award Date', value: formatDate(opp.awardDate) },
    { label: 'Award Amount', value: formatCurrency(opp.awardAmount) },
  ];

  return (
    <Box>
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Incumbent Information
        </Typography>
        <KeyFactsGrid facts={incumbentFacts} columns={2} />
      </Paper>

      {/* Burn Rate Chart */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <BurnRateChart
          data={burnRateData?.monthlyBreakdown?.map(m => ({ month: m.yearMonth, amount: m.amount })) ?? []}
          totalObligated={burnRateData?.totalObligated}
          baseAndAllOptions={burnRateData?.baseAndAllOptions ?? undefined}
          title="Previous Contract Burn Rate"
        />
      </Paper>

      {/* Related awards table */}
      {opp.relatedAwards.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            Related Awards
          </Typography>
          <DataTable
            columns={RELATED_AWARD_COLUMNS}
            rows={opp.relatedAwards}
            getRowId={(row: RelatedAwardDto) => row.contractId}
            onRowClick={(params) => {
              navigate(`/awards/${encodeURIComponent(params.row.contractId)}`);
            }}
          />
        </Paper>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab: Competition
// ---------------------------------------------------------------------------

const MARKET_SHARE_COLUMNS: GridColDef<MarketShareDto>[] = [
  {
    field: 'vendorName',
    headerName: 'Vendor',
    flex: 2,
    minWidth: 200,
  },
  { field: 'vendorUei', headerName: 'UEI', flex: 1, minWidth: 130 },
  { field: 'awardCount', headerName: 'Awards', width: 90, type: 'number' },
  {
    field: 'totalValue',
    headerName: 'Total Value',
    width: 140,
    type: 'number',
    renderCell: ({ value }) => <CurrencyDisplay value={value} compact />,
  },
  {
    field: 'averageValue',
    headerName: 'Avg Value',
    width: 130,
    type: 'number',
    renderCell: ({ value }) => <CurrencyDisplay value={value} compact />,
  },
  {
    field: 'lastAwardDate',
    headerName: 'Last Award',
    width: 120,
    renderCell: ({ value }) => (value ? formatDate(value) : '--'),
  },
];

function CompetitionTab({ opp }: { opp: OpportunityDetail }) {
  const navigate = useNavigate();
  const summary = opp.usaspendingAward;

  const summaryFacts = summary
    ? [
        { label: 'Award ID', value: summary.generatedUniqueAwardId },
        { label: 'Recipient', value: summary.recipientName ?? '--' },
        { label: 'Recipient UEI', value: summary.recipientUei ?? '--' },
        { label: 'Total Obligation', value: formatCurrency(summary.totalObligation) },
        { label: 'Ceiling', value: formatCurrency(summary.baseAndAllOptionsValue) },
        {
          label: 'Period',
          value:
            summary.startDate || summary.endDate
              ? `${formatDate(summary.startDate)} - ${formatDate(summary.endDate)}`
              : '--',
        },
      ]
    : [];

  return (
    <Box>
      {/* USAspending summary */}
      {summary ? (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            USAspending Summary
          </Typography>
          <KeyFactsGrid facts={summaryFacts} columns={2} />
        </Paper>
      ) : (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <EmptyState
            title="No USAspending Data"
            message="No USAspending summary available for this opportunity."
          />
        </Paper>
      )}

      {/* Related awards by NAICS */}
      {opp.relatedAwards.length > 0 ? (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            Related Awards
          </Typography>
          <DataTable
            columns={RELATED_AWARD_COLUMNS}
            rows={opp.relatedAwards}
            getRowId={(row: RelatedAwardDto) => row.contractId}
            onRowClick={(params) => {
              navigate(`/awards/${encodeURIComponent(params.row.contractId)}`);
            }}
          />
        </Paper>
      ) : (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <EmptyState
            title="No Related Awards"
            message="No related awards found for this opportunity."
          />
        </Paper>
      )}

      {/* Market share by NAICS */}
      <MarketShareSection naicsCode={opp.naicsCode} navigate={navigate} />
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Market Share Section (within Competition tab)
// ---------------------------------------------------------------------------

function MarketShareSection({
  naicsCode,
  navigate,
}: {
  naicsCode?: string | null;
  navigate: ReturnType<typeof useNavigate>;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.awards.marketShare(naicsCode ?? ''),
    queryFn: () => getMarketShare(naicsCode!, 10),
    staleTime: 5 * 60 * 1000,
    enabled: !!naicsCode,
  });

  if (!naicsCode) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <EmptyState
          title="No NAICS Code"
          message="Cannot show market share without a NAICS code."
        />
      </Paper>
    );
  }

  if (isLoading) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Market Share — NAICS {naicsCode}
        </Typography>
        <LoadingState message="Loading market share data..." />
      </Paper>
    );
  }

  if (isError || !data) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <EmptyState
          title="Market Share Unavailable"
          message="Could not load market share data."
        />
      </Paper>
    );
  }

  if (data.length < 3) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <EmptyState
          title={`Insufficient Data for NAICS ${naicsCode}`}
          message="Fewer than 3 vendors found. Award data coverage depends on ETL load history."
        />
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 2 }}>
        Top Vendors — NAICS {naicsCode}
      </Typography>
      <Box sx={{ width: '100%', height: Math.max(200, data.length * 40) }}>
        <BarChart
          dataset={data.map((d) => ({
            vendor:
              d.vendorName.length > 30
                ? d.vendorName.slice(0, 27) + '...'
                : d.vendorName,
            value: d.totalValue,
          }))}
          yAxis={[{ scaleType: 'band', dataKey: 'vendor' }]}
          xAxis={[
            {
              valueFormatter: (v: number) => formatCurrency(v) ?? '',
            },
          ]}
          series={[
            {
              dataKey: 'value',
              label: 'Total Award Value',
              valueFormatter: (v) =>
                formatCurrency(v as number | null) ?? '',
            },
          ]}
          layout="horizontal"
          margin={{ left: 200 }}
          hideLegend
        />
      </Box>
      <Divider sx={{ my: 2 }} />
      <DataTable
        columns={MARKET_SHARE_COLUMNS}
        rows={data}
        getRowId={(row: MarketShareDto) => row.vendorUei}
        onRowClick={(params) => {
          navigate(`/entities/${encodeURIComponent(params.row.vendorUei)}`);
        }}
      />
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Tab: Prospect
// ---------------------------------------------------------------------------

function ProspectTab({
  opp,
  onTrack,
  isTracking,
}: {
  opp: OpportunityDetail;
  onTrack: () => void;
  isTracking: boolean;
}) {
  const prospect = opp.prospect;

  if (!prospect) {
    return (
      <EmptyState
        title="Not Tracked"
        message="This opportunity is not yet being tracked as a prospect."
        action={
          <Button
            variant="contained"
            startIcon={<TrackChangesIcon />}
            onClick={onTrack}
            disabled={isTracking}
          >
            Track as Prospect
          </Button>
        }
      />
    );
  }

  const facts = [
    { label: 'Status', value: <StatusChip status={prospect.status} /> },
    { label: 'Priority', value: prospect.priority ?? '--' },
    {
      label: 'Go/No-Go Score',
      value: prospect.goNoGoScore != null ? `${prospect.goNoGoScore}` : '--',
    },
    {
      label: 'Win Probability',
      value: prospect.winProbability != null ? `${prospect.winProbability}%` : '--',
    },
    { label: 'Assigned To', value: prospect.assignedTo ?? '--' },
  ];

  return (
    <Box>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Prospect Summary
        </Typography>
        <KeyFactsGrid facts={facts} columns={2} />
        <Divider sx={{ my: 2 }} />
        <Button
          component={RouterLink}
          to={`/prospects/${prospect.prospectId}`}
          variant="outlined"
        >
          View Full Prospect Detail
        </Button>
      </Paper>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Save Search Similar Dialog
// ---------------------------------------------------------------------------

function SaveSearchSimilarDialog({
  open,
  onClose,
  opp,
}: {
  open: boolean;
  onClose: () => void;
  opp: OpportunityDetail;
}) {
  const [name, setName] = useState('');
  const [notifications, setNotifications] = useState(false);
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      createSavedSearch({
        searchName: name,
        filterCriteria: {
          naicsCodes: opp.naicsCode ? [opp.naicsCode] : null,
          setAsideCodes: opp.setAsideCode ? [opp.setAsideCode] : null,
        },
        notificationEnabled: notifications,
      }),
    onSuccess: () => {
      enqueueSnackbar('Saved search created', { variant: 'success' });
      queryClient.invalidateQueries({ queryKey: queryKeys.savedSearches.all });
      handleClose();
    },
    onError: () => {
      enqueueSnackbar('Failed to create saved search', { variant: 'error' });
    },
  });

  function handleClose() {
    setName('');
    setNotifications(false);
    onClose();
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Save Similar Search</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          required
          margin="dense"
          label="Search Name"
          fullWidth
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Pre-populated criteria:
          </Typography>
          {opp.naicsCode && (
            <Typography variant="body2">NAICS: {opp.naicsCode}</Typography>
          )}
          {opp.setAsideCode && (
            <Typography variant="body2">Set-aside: {opp.setAsideCode}</Typography>
          )}
        </Box>
        <FormControlLabel
          control={
            <Checkbox
              checked={notifications}
              onChange={(e) => setNotifications(e.target.checked)}
            />
          }
          label="Enable notifications"
          sx={{ mt: 1 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          onClick={() => mutation.mutate()}
          variant="contained"
          disabled={!name.trim() || mutation.isPending}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function OpportunityDetailPage() {
  const { noticeId } = useParams<{ noticeId: string }>();
  const decodedId = noticeId ? decodeURIComponent(noticeId) : '';
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();
  const [saveSearchOpen, setSaveSearchOpen] = useState(false);

  const {
    data: opp,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.opportunities.detail(decodedId),
    queryFn: () => getOpportunity(decodedId),
    enabled: !!decodedId,
    staleTime: 5 * 60 * 1000,
  });

  const trackMutation = useMutation({
    mutationFn: () => createProspect({ noticeId: decodedId }),
    onSuccess: (data) => {
      enqueueSnackbar('Opportunity added to pipeline', { variant: 'success' });
      queryClient.invalidateQueries({
        queryKey: queryKeys.opportunities.detail(decodedId),
      });
      navigate(`/prospects/${data.prospect.prospectId}`);
    },
    onError: () => {
      enqueueSnackbar('Failed to track opportunity', { variant: 'error' });
    },
  });

  // --- Loading / Error / Not Found ---
  if (isLoading) {
    return (
      <Box>
        <BackToSearch searchPath="/opportunities" />
        <LoadingState message="Loading opportunity details..." />
      </Box>
    );
  }

  if (isError) {
    return (
      <Box>
        <BackToSearch searchPath="/opportunities" />
        <ErrorState
          title="Failed to load opportunity"
          message="An error occurred while loading this opportunity. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  if (!opp) {
    return (
      <Box>
        <BackToSearch searchPath="/opportunities" />
        <ErrorState
          title="Opportunity not found"
          message="The requested opportunity could not be found."
        />
      </Box>
    );
  }

  // --- Set-aside chip ---
  const setAsideLabel = [opp.setAsideCode, opp.setAsideDescription]
    .filter(Boolean)
    .join(' - ');

  // --- Tabs ---
  const tabs = [
    {
      label: 'Overview',
      value: 'overview',
      content: <OverviewTab opp={opp} />,
    },
    {
      label: 'History & Incumbent Intel',
      value: 'history',
      content: <HistoryTab opp={opp} />,
    },
    {
      label: 'Competition',
      value: 'competition',
      content: <CompetitionTab opp={opp} />,
    },
    {
      label: 'Prospect',
      value: 'prospect',
      content: (
        <ProspectTab
          opp={opp}
          onTrack={() => trackMutation.mutate()}
          isTracking={trackMutation.isPending}
        />
      ),
    },
  ];

  return (
    <TabbedDetailPage tabs={tabs}>
      {/* Back button */}
      <BackToSearch searchPath="/opportunities" />

      {/* Header */}
      <PageHeader
        title={opp.title ?? 'Untitled Opportunity'}
        subtitle={opp.solicitationNumber ?? undefined}
        actions={
          <Box sx={{ display: 'flex', gap: 1 }}>
            {(opp.naicsCode || opp.setAsideCode) && (
              <Button
                variant="outlined"
                startIcon={<SavedSearchIcon />}
                onClick={() => setSaveSearchOpen(true)}
              >
                Save Search Similar
              </Button>
            )}
            {opp.prospect ? (
              <Button
                variant="outlined"
                component={RouterLink}
                to={`/prospects/${opp.prospect.prospectId}`}
              >
                View Prospect
              </Button>
            ) : (
              <Button
                variant="contained"
                startIcon={<TrackChangesIcon />}
                onClick={() => trackMutation.mutate()}
                disabled={trackMutation.isPending}
              >
                Track as Prospect
              </Button>
            )}
          </Box>
        }
      />

      {/* Save Search Similar Dialog */}
      <SaveSearchSimilarDialog
        open={saveSearchOpen}
        onClose={() => setSaveSearchOpen(false)}
        opp={opp}
      />

      {/* Summary row: deadline, chips, estimated value */}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 1.5,
          mb: 3,
        }}
      >
        <DeadlineCountdown deadline={opp.responseDeadline ?? null} />

        {setAsideLabel && <Chip label={setAsideLabel} size="small" color="secondary" />}
        {opp.naicsCode && (
          <Chip label={`NAICS ${opp.naicsCode}`} size="small" variant="outlined" />
        )}
        {opp.departmentName && (
          <Chip label={opp.departmentName} size="small" variant="outlined" />
        )}
        {opp.active != null && (
          <Chip
            label={opp.active === 'Yes' ? 'Active' : 'Inactive'}
            color={opp.active === 'Yes' ? 'success' : 'default'}
            size="small"
          />
        )}

        {/* Estimated value -- prominent */}
        {opp.estimatedContractValue != null && (
          <Typography variant="h6" component="span" sx={{ ml: 'auto', fontWeight: 700 }}>
            <CurrencyDisplay value={opp.estimatedContractValue} compact />
          </Typography>
        )}
      </Box>
    </TabbedDetailPage>
  );
}
