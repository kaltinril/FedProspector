import { useMemo, useState } from 'react';
import { useParams, useNavigate, useLocation, Link as RouterLink } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import type { GridColDef } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import Skeleton from '@mui/material/Skeleton';
import FormControlLabel from '@mui/material/FormControlLabel';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import SavedSearchIcon from '@mui/icons-material/SavedSearch';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import DescriptionIcon from '@mui/icons-material/Description';
import TableChartIcon from '@mui/icons-material/TableChart';
import ImageIcon from '@mui/icons-material/Image';
import ContactPhoneIcon from '@mui/icons-material/ContactPhone';

import { AgencyLink } from '@/components/shared/AgencyLink';
import { PageHeader } from '@/components/shared/PageHeader';
import { BackToSearch } from '@/components/shared/BackToSearch';
import { TabbedDetailPage } from '@/components/shared/TabbedDetailPage';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { DeadlineCountdown } from '@/components/shared/DeadlineCountdown';
import { BurnRateChart } from '@/components/shared/BurnRateChart';
import PWinGauge from '@/components/shared/PWinGauge';

import { DataTable } from '@/components/shared/DataTable';
import { StatusChip } from '@/components/shared/StatusChip';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { EmptyState } from '@/components/shared/EmptyState';
import QualificationPWinTab from './QualificationPWinTab';
import CompetitiveIntelTab from './CompetitiveIntelTab';
import DocumentIntelligenceTab from './DocumentIntelligenceTab';
import { getOpportunity, getQualification, getPWin, fetchDescription } from '@/api/opportunities';
import { getBurnRate } from '@/api/awards';
import { createProspect } from '@/api/prospects';
import { createSavedSearch } from '@/api/savedSearches';
import { queryKeys } from '@/queries/queryKeys';
import { formatDate, formatDateTime } from '@/utils/dateFormatters';
import { formatCurrency } from '@/utils/formatters';
import { buildPlaceOfPerformance } from '@/utils/format';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';

import type { OpportunityDetail, QScoreFactorDto, RelatedAwardDto, ResourceLinkDto } from '@/types/api';

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
// Resource Links (collapsible)
// ---------------------------------------------------------------------------

const RESOURCE_LINKS_LIMIT = 5;

function ResourceLinksSection({ resourceLinks }: { resourceLinks: { url: string; label: string; contentType: string | null }[] }) {
  const [expanded, setExpanded] = useState(false);
  const needsCollapse = resourceLinks.length > RESOURCE_LINKS_LIMIT;
  const visible = needsCollapse && !expanded ? resourceLinks.slice(0, RESOURCE_LINKS_LIMIT) : resourceLinks;

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
        Resource Links ({resourceLinks.length})
      </Typography>
      {visible.map((rl, idx) => (
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
      {needsCollapse && (
        <Button
          size="small"
          onClick={() => setExpanded((prev) => !prev)}
          sx={{ textTransform: 'none', fontSize: '0.75rem' }}
        >
          {expanded ? 'Show fewer' : `Show all ${resourceLinks.length} links`}
        </Button>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Qualification Summary (compact, for Overview tab)
// ---------------------------------------------------------------------------

const QUAL_STATUS_COLOR: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  Qualified: 'success',
  'Partially Qualified': 'warning',
  'Not Qualified': 'error',
};

function QualificationSummary({
  noticeId,
  onViewDetails,
}: {
  noticeId: string;
  onViewDetails: () => void;
}) {
  const { data: qual, isLoading, isError } = useQuery({
    queryKey: queryKeys.opportunities.qualification(noticeId),
    queryFn: () => getQualification(noticeId),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
        Qualification Summary
      </Typography>
      {isLoading ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Skeleton variant="rounded" width={140} height={24} />
          <Skeleton variant="text" width={180} />
        </Box>
      ) : isError || !qual ? (
        <Typography variant="body2" color="text.secondary">
          Could not load qualification data.
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <Chip
            label={qual.overallStatus}
            color={QUAL_STATUS_COLOR[qual.overallStatus] ?? 'default'}
            size="small"
          />
          <Typography variant="body2" color="text.secondary">
            {qual.passCount} Pass &middot; {qual.failCount} Fail &middot; {qual.warningCount} Warning
          </Typography>
          <Button size="small" onClick={onViewDetails}>
            View details
          </Button>
        </Box>
      )}
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Tab: Overview
// ---------------------------------------------------------------------------

function OverviewTab({
  opp,
  onViewQualification,
  qScoreState,
  pWinScore,
  pWinCategory,
  pWinLoading,
}: {
  opp: OpportunityDetail;
  onViewQualification: () => void;
  qScoreState?: { qScore: number; qScoreCategory: string; qScoreFactors: QScoreFactorDto[] };
  pWinScore?: number;
  pWinCategory?: string;
  pWinLoading?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();

  const hasDescription = !!opp.descriptionText;
  const canFetchDescription = !hasDescription && !!opp.descriptionUrl;
  const description = opp.descriptionText ?? '';
  const isLong = description.length > 300;
  const locationIndicator = getLocationIndicator(opp.popCountry, opp.popState);
  const resourceLinks = getResourceLinksForDisplay(opp);

  const fetchDescriptionMutation = useMutation({
    mutationFn: () => fetchDescription(opp.noticeId),
    onSuccess: () => {
      enqueueSnackbar('Description fetched from SAM.gov', { variant: 'success' });
      queryClient.invalidateQueries({
        queryKey: queryKeys.opportunities.detail(opp.noticeId),
      });
    },
    onError: () => {
      enqueueSnackbar('Failed to fetch description from SAM.gov', { variant: 'error' });
    },
  });

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
        value: `${buildPlaceOfPerformance(opp, '--')} (${locationIndicator})`,
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
      {(hasDescription || canFetchDescription) && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Description
          </Typography>
          {hasDescription ? (
            <>
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
            </>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                No description loaded. A description URL is available on SAM.gov.
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={
                  fetchDescriptionMutation.isPending ? (
                    <CircularProgress size={16} />
                  ) : (
                    <CloudDownloadIcon />
                  )
                }
                disabled={fetchDescriptionMutation.isPending}
                onClick={() => fetchDescriptionMutation.mutate()}
              >
                Fetch Description from SAM.gov
              </Button>
            </Box>
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

        {/* Resource links — collapsed after first 5 */}
        {resourceLinks.length > 0 && (
          <ResourceLinksSection resourceLinks={resourceLinks} />
        )}
      </Paper>

      {/* Points of Contact */}
      {opp.pointsOfContact && opp.pointsOfContact.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
            <ContactPhoneIcon fontSize="small" color="action" />
            <Typography variant="subtitle2">
              Points of Contact
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {opp.pointsOfContact.map((poc, i) => (
              <Box key={i} sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="body2" fontWeight="bold">
                    {poc.fullName}
                  </Typography>
                  <Chip label={poc.pocType} size="small" variant="outlined" />
                  {poc.title && (
                    <Typography variant="body2" color="text.secondary">
                      {poc.title}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  {poc.email && (
                    <Link href={`mailto:${poc.email}`} variant="body2">
                      {poc.email}
                    </Link>
                  )}
                  {poc.phone && (
                    <Typography variant="body2" color="text.secondary">
                      {poc.phone}
                    </Typography>
                  )}
                  {poc.fax && (
                    <Typography variant="body2" color="text.secondary">
                      Fax: {poc.fax}
                    </Typography>
                  )}
                </Box>
                {i < opp.pointsOfContact!.length - 1 && <Divider sx={{ mt: 1 }} />}
              </Box>
            ))}
          </Box>
        </Paper>
      )}

      {/* qScore (passed from Recommended page) */}
      {qScoreState && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Typography variant="subtitle2">qScore</Typography>
            <Chip
              label={qScoreState.qScore}
              size="small"
              color={qScoreState.qScore >= 70 ? 'success' : qScoreState.qScore >= 40 ? 'warning' : 'error'}
            />
            {qScoreState.qScoreFactors.length > 0 && (
              <Typography variant="body2" color="text.secondary">
                {qScoreState.qScoreFactors.map((f) => `${f.name} ${f.points}/${f.maxPoints}`).join(' \u00b7 ')}
              </Typography>
            )}
          </Box>
        </Paper>
      )}

      {/* Win Probability */}
      {(pWinLoading || (pWinScore != null && pWinCategory)) && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
            Win Probability
          </Typography>
          {pWinLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={32} />
            </Box>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <PWinGauge score={pWinScore!} category={pWinCategory!} size="medium" />
            </Box>
          )}
        </Paper>
      )}

      {/* Qualification Summary */}
      <QualificationSummary noticeId={opp.noticeId} onViewDetails={onViewQualification} />

      {/* Amendment History */}
      {opp.amendments && opp.amendments.length > 0 && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" gutterBottom>
            Amendment History
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            This solicitation has {opp.amendments.length + 1} version{opp.amendments.length > 0 ? 's' : ''}. You are viewing the latest.
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
            <Table size="small" sx={{ minWidth: 640 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Posted</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Awardee</TableCell>
                  <TableCell align="right">Award $</TableCell>
                  <TableCell>Response Deadline</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {opp.amendments.map((a) => {
                  const isAwardNotice = a.type === 'Award Notice';
                  return (
                    <TableRow key={a.noticeId}>
                      <TableCell>{formatDate(a.postedDate)}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {a.type ?? '--'}
                          {isAwardNotice && (
                            <Chip label="Awarded" size="small" color="success" />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>{isAwardNotice && a.awardeeName ? a.awardeeName : '--'}</TableCell>
                      <TableCell align="right">
                        {isAwardNotice && a.awardAmount != null ? formatCurrency(a.awardAmount) : '--'}
                      </TableCell>
                      <TableCell>{formatDate(a.responseDeadline)}</TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          component={RouterLink}
                          to={`/opportunities/${encodeURIComponent(a.noticeId)}`}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
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
  const hasAmendments = opp.amendments && opp.amendments.length > 0;

  const firstAward = opp.relatedAwards?.[0];
  const { data: burnRateData } = useQuery({
    queryKey: queryKeys.awards.burnRate(firstAward?.contractId ?? ''),
    queryFn: () => getBurnRate(firstAward!.contractId),
    staleTime: 5 * 60 * 1000,
    enabled: isRecompete && !!firstAward?.contractId,
  });

  const incumbentFacts = isRecompete
    ? [
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
      ]
    : null;

  // Show empty state only when there is truly no history data at all
  if (!isRecompete && !hasAmendments && opp.relatedAwards.length === 0) {
    return (
      <EmptyState
        title="No History Available"
        message="No amendment history, awards, or incumbent information available for this opportunity."
        icon={<InfoOutlinedIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />}
      />
    );
  }

  return (
    <Box>
      {/* Incumbent section — only for recompetes */}
      {incumbentFacts && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            Incumbent Information
          </Typography>
          <KeyFactsGrid facts={incumbentFacts} columns={2} />
        </Paper>
      )}

      {/* Burn Rate Chart — only for recompetes with contract data */}
      {isRecompete && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <BurnRateChart
            data={burnRateData?.monthlyBreakdown?.map(m => ({ month: m.yearMonth, amount: m.amount })) ?? []}
            totalObligated={burnRateData?.totalObligated}
            baseAndAllOptions={burnRateData?.baseAndAllOptions ?? undefined}
            title="Previous Contract Burn Rate"
          />
        </Paper>
      )}

      {/* Solicitation Timeline — amendment history for all opportunities */}
      {hasAmendments && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Solicitation Timeline
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            This solicitation has {opp.amendments!.length + 1} version{opp.amendments!.length > 0 ? 's' : ''} in the SAM.gov record.
          </Typography>
          <TableContainer sx={{ overflowX: 'auto' }}>
            <Table size="small" sx={{ minWidth: 640 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Posted</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Awardee</TableCell>
                  <TableCell align="right">Award $</TableCell>
                  <TableCell>Response Deadline</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {opp.amendments!.map((a) => {
                  const isAwardNotice = a.type === 'Award Notice';
                  return (
                    <TableRow key={a.noticeId}>
                      <TableCell>{formatDate(a.postedDate)}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {a.type ?? '--'}
                          {isAwardNotice && (
                            <Chip label="Awarded" size="small" color="success" />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>{isAwardNotice && a.awardeeName ? a.awardeeName : '--'}</TableCell>
                      <TableCell align="right">
                        {isAwardNotice && a.awardAmount != null ? formatCurrency(a.awardAmount) : '--'}
                      </TableCell>
                      <TableCell>{formatDate(a.responseDeadline)}</TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          component={RouterLink}
                          to={`/opportunities/${encodeURIComponent(a.noticeId)}`}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

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
  const location = useLocation();
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();
  const [saveSearchOpen, setSaveSearchOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  // qScore passed from RecommendedOpportunitiesPage via navigation state
  const locState = location.state as { qScore?: number; qScoreCategory?: string; qScoreFactors?: QScoreFactorDto[] } | null;
  const qScoreState = locState?.qScore != null
    ? { qScore: locState.qScore, qScoreCategory: locState.qScoreCategory ?? '', qScoreFactors: locState.qScoreFactors ?? [] }
    : undefined;

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

  const { data: pWinData, isLoading: pWinLoading } = useQuery({
    queryKey: queryKeys.opportunities.pwin(decodedId),
    queryFn: () => getPWin(decodedId),
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
      content: (
        <OverviewTab
          opp={opp}
          onViewQualification={() => setActiveTab('qualification')}
          qScoreState={qScoreState}
          pWinScore={pWinData?.score}
          pWinCategory={pWinData?.category}
          pWinLoading={pWinLoading}
        />
      ),
    },
    {
      label: 'Document Intel',
      value: 'documentIntel',
      content: <DocumentIntelligenceTab noticeId={decodedId} />,
    },
    {
      label: 'Qualification & pWin',
      value: 'qualification',
      content: <QualificationPWinTab opp={opp} />,
    },
    {
      label: 'Competitive Intel',
      value: 'competitive',
      content: <CompetitiveIntelTab opp={opp} />,
    },
    {
      label: 'History & Awards',
      value: 'history',
      content: <HistoryTab opp={opp} />,
    },
    {
      label: 'Actions',
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
    <TabbedDetailPage tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab}>
      {/* Back button */}
      <BackToSearch searchPath="/opportunities" />

      {/* Header */}
      <PageHeader
        title={opp.title ?? 'Untitled Opportunity'}
        subtitle={opp.solicitationNumber ?? undefined}
        actions={
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
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

      {/* Auto-match reasoning banner (Phase 91-D2) */}
      {opp.prospect?.source && opp.prospect.source !== 'MANUAL' && (
        <Paper
          variant="outlined"
          sx={{
            p: 1.5,
            mb: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            bgcolor: 'info.50',
            borderColor: 'info.light',
          }}
        >
          <AutoAwesomeIcon color="info" fontSize="small" />
          <Typography variant="body2" color="info.dark">
            Auto-matched via{' '}
            {opp.prospect.source === 'AUTO_RECOMPETE' ? 'recompete detection' : 'saved search'}
          </Typography>
          {opp.naicsCode && (
            <Chip label={`NAICS ${opp.naicsCode}`} size="small" variant="outlined" color="info" />
          )}
          {opp.setAsideCode && (
            <Chip label={opp.setAsideCode} size="small" variant="outlined" color="info" />
          )}
          {opp.prospect.winProbability != null && (
            <Chip label={`pWin ${opp.prospect.winProbability}%`} size="small" color="info" />
          )}
        </Paper>
      )}

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
          <Chip label={<AgencyLink name={opp.departmentName} agencyCode={opp.contractingOfficeId ?? undefined} />} size="small" variant="outlined" />
        )}
        {opp.active != null && (
          <Chip
            label={opp.active === 'Y' ? 'Active' : 'Inactive'}
            color={opp.active === 'Y' ? 'success' : 'default'}
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
