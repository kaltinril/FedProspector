import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import DescriptionIcon from '@mui/icons-material/Description';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { getDocumentIntelligence, requestAnalysis } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import type { IntelSourceDto, AttachmentSummaryDto } from '@/types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CONFIDENCE_COLOR: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  high: 'success',
  medium: 'warning',
  low: 'error',
};

function getConfidenceColor(confidence: string): 'success' | 'warning' | 'error' | 'default' {
  return CONFIDENCE_COLOR[confidence.toLowerCase()] ?? 'default';
}

const METHOD_LABELS: Record<string, string> = {
  keyword: 'Keyword',
  ai_haiku: 'AI (Haiku)',
  ai_sonnet: 'AI (Sonnet)',
};

function formatFileSize(bytes: number | undefined | null): string {
  if (bytes == null) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Intel Card (one extracted field with provenance)
// ---------------------------------------------------------------------------

interface IntelCardProps {
  label: string;
  fieldName: string;
  value: string | null | undefined;
  sources: IntelSourceDto[];
}

function IntelCard({ label, fieldName, value, sources }: IntelCardProps) {
  const [expanded, setExpanded] = useState(false);
  if (!value) return null;

  const fieldSources = sources.filter((s) => s.fieldName === fieldName);
  const topSource = fieldSources[0];
  const confidence = topSource?.confidence ?? 'unknown';
  const method = topSource?.extractionMethod ?? '';

  return (
    <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0 }}>
            {method && (
              <Chip
                label={METHOD_LABELS[method] ?? method}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.65rem', height: 20 }}
              />
            )}
            <Chip
              label={confidence}
              size="small"
              color={getConfidenceColor(confidence)}
              sx={{ fontSize: '0.65rem', height: 20 }}
            />
          </Box>
        </Box>
        <Typography variant="body1" sx={{ fontWeight: 600 }}>
          {value}
        </Typography>
      </CardContent>

      {/* Source provenance (expandable) */}
      {fieldSources.length > 0 && (
        <Box sx={{ px: 2, pb: 1 }}>
          <Box
            sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
            onClick={() => setExpanded((prev) => !prev)}
          >
            <Typography variant="caption" color="text.secondary">
              View Sources ({fieldSources.length})
            </Typography>
            <IconButton size="small" sx={{ ml: 'auto', transform: expanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
              <ExpandMoreIcon fontSize="small" />
            </IconButton>
          </Box>
          <Collapse in={expanded}>
            {fieldSources.map((src, idx) => (
              <Box key={idx} sx={{ mt: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                {src.sourceFilename && (
                  <Typography variant="caption" color="text.secondary" display="block">
                    {src.sourceFilename}
                    {src.pageNumber != null ? `, p.${src.pageNumber}` : ''}
                  </Typography>
                )}
                {src.matchedText && (
                  <Typography variant="body2" sx={{ mt: 0.5, fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {src.surroundingContext ? (
                      <>
                        {src.surroundingContext.split(src.matchedText)[0]}
                        <Box component="mark" sx={{ bgcolor: 'warning.light', px: 0.25 }}>
                          {src.matchedText}
                        </Box>
                        {src.surroundingContext.split(src.matchedText).slice(1).join(src.matchedText)}
                      </>
                    ) : (
                      src.matchedText
                    )}
                  </Typography>
                )}
              </Box>
            ))}
          </Collapse>
        </Box>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// List Card (labor categories, key requirements)
// ---------------------------------------------------------------------------

interface ListCardProps {
  label: string;
  fieldName: string;
  items: string[];
  sources: IntelSourceDto[];
}

function ListCard({ label, fieldName, items, sources }: ListCardProps) {
  const [expanded, setExpanded] = useState(false);
  if (items.length === 0) return null;

  const fieldSources = sources.filter((s) => s.fieldName === fieldName);
  const topSource = fieldSources[0];
  const confidence = topSource?.confidence ?? 'unknown';

  return (
    <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Chip
            label={confidence}
            size="small"
            color={getConfidenceColor(confidence)}
            sx={{ fontSize: '0.65rem', height: 20 }}
          />
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {items.map((item, idx) => (
            <Chip key={idx} label={item} size="small" variant="outlined" />
          ))}
        </Box>
      </CardContent>

      {fieldSources.length > 0 && (
        <Box sx={{ px: 2, pb: 1 }}>
          <Box
            sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
            onClick={() => setExpanded((prev) => !prev)}
          >
            <Typography variant="caption" color="text.secondary">
              View Sources ({fieldSources.length})
            </Typography>
            <IconButton size="small" sx={{ ml: 'auto', transform: expanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
              <ExpandMoreIcon fontSize="small" />
            </IconButton>
          </Box>
          <Collapse in={expanded}>
            {fieldSources.map((src, idx) => (
              <Box key={idx} sx={{ mt: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                {src.sourceFilename && (
                  <Typography variant="caption" color="text.secondary" display="block">
                    {src.sourceFilename}
                    {src.pageNumber != null ? `, p.${src.pageNumber}` : ''}
                  </Typography>
                )}
              </Box>
            ))}
          </Collapse>
        </Box>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Attachment Status Chip
// ---------------------------------------------------------------------------

const DOWNLOAD_STATUS_COLOR: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  downloaded: 'success',
  pending: 'warning',
  failed: 'error',
};

const EXTRACTION_STATUS_COLOR: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  extracted: 'success',
  analyzed: 'success',
  pending: 'warning',
  failed: 'error',
  skipped: 'default',
};

// ---------------------------------------------------------------------------
// Attachments Table
// ---------------------------------------------------------------------------

function AttachmentsTable({ attachments }: { attachments: AttachmentSummaryDto[] }) {
  if (attachments.length === 0) return null;

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 2 }}>
        Attachments ({attachments.length})
      </Typography>
      <TableContainer sx={{ overflowX: 'auto' }}>
        <Table size="small" sx={{ minWidth: 640 }}>
          <TableHead>
            <TableRow>
              <TableCell>Filename</TableCell>
              <TableCell>Type</TableCell>
              <TableCell align="right">Size</TableCell>
              <TableCell align="right">Pages</TableCell>
              <TableCell>Download</TableCell>
              <TableCell>Extraction</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {attachments.map((att) => (
              <TableRow key={att.attachmentId}>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <DescriptionIcon fontSize="small" color="action" />
                    <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                      {att.filename}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    {att.contentType ?? '--'}
                  </Typography>
                </TableCell>
                <TableCell align="right">{formatFileSize(att.fileSizeBytes)}</TableCell>
                <TableCell align="right">{att.pageCount ?? '--'}</TableCell>
                <TableCell>
                  <Chip
                    label={att.downloadStatus}
                    size="small"
                    color={DOWNLOAD_STATUS_COLOR[att.downloadStatus.toLowerCase()] ?? 'default'}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={att.extractionStatus}
                    size="small"
                    color={EXTRACTION_STATUS_COLOR[att.extractionStatus.toLowerCase()] ?? 'default'}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Main Tab Component
// ---------------------------------------------------------------------------

export default function DocumentIntelligenceTab({ noticeId }: { noticeId: string }) {
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();

  const {
    data: intel,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: queryKeys.opportunities.documentIntelligence(noticeId),
    queryFn: () => getDocumentIntelligence(noticeId),
    staleTime: 5 * 60 * 1000,
    retry: (failureCount, err) => {
      // Treat 404 as empty state, do not retry
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return false;
      }
      return failureCount < 2;
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => requestAnalysis(noticeId, 'haiku'),
    onSuccess: () => {
      enqueueSnackbar('Analysis requested. Results will appear after processing.', { variant: 'success' });
      // Refetch after a short delay to pick up status change
      setTimeout(() => {
        queryClient.invalidateQueries({
          queryKey: queryKeys.opportunities.documentIntelligence(noticeId),
        });
      }, 2000);
    },
    onError: () => {
      enqueueSnackbar('Failed to request analysis', { variant: 'error' });
    },
  });

  // --- Loading ---
  if (isLoading) {
    return <LoadingState message="Loading document intelligence..." />;
  }

  // --- 404 / No data ---
  const is404 =
    isError &&
    error &&
    typeof error === 'object' &&
    'response' in error &&
    (error as { response?: { status?: number } }).response?.status === 404;

  if (is404 || (!isError && !intel)) {
    return (
      <EmptyState
        title="No Document Intelligence Available"
        message="Attachments must be downloaded and analyzed via the CLI pipeline before intelligence can be extracted."
        icon={<DescriptionIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />}
        action={
          <Button
            variant="contained"
            startIcon={analyzeMutation.isPending ? <CircularProgress size={18} color="inherit" /> : <AnalyticsIcon />}
            disabled={analyzeMutation.isPending}
            onClick={() => analyzeMutation.mutate()}
          >
            {analyzeMutation.isPending ? 'Requesting...' : 'Analyze with AI'}
          </Button>
        }
      />
    );
  }

  // --- Error ---
  if (isError) {
    return (
      <ErrorState
        title="Failed to load document intelligence"
        message="An error occurred while loading document intelligence for this opportunity."
      />
    );
  }

  // --- Render Data ---
  const sources = intel.sources ?? [];

  // Build intel card entries
  type IntelField = { label: string; fieldName: string; value: string | null | undefined };
  const intelFields: IntelField[] = [
    { label: 'Security Clearance', fieldName: 'clearance_level', value: [intel.clearanceLevel, intel.clearanceScope].filter(Boolean).join(' - ') || intel.clearanceRequired || null },
    { label: 'Evaluation Method', fieldName: 'eval_method', value: intel.evalMethod },
    { label: 'Contract Vehicle', fieldName: 'vehicle_type', value: intel.vehicleType },
    {
      label: 'Recompete Status',
      fieldName: 'is_recompete',
      value: intel.isRecompete != null
        ? `${intel.isRecompete}${intel.incumbentName ? ` (Incumbent: ${intel.incumbentName})` : ''}`
        : null,
    },
    { label: 'Scope Summary', fieldName: 'scope_summary', value: intel.scopeSummary },
    { label: 'Period of Performance', fieldName: 'period_of_performance', value: intel.periodOfPerformance },
  ];

  const hasAnyIntel = intelFields.some((f) => f.value) || intel.laborCategories.length > 0 || intel.keyRequirements.length > 0;

  return (
    <Box>
      {/* Overall confidence + stats */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <Typography variant="subtitle2">Document Intelligence</Typography>
          <Chip
            label={`Confidence: ${intel.overallConfidence}`}
            color={getConfidenceColor(intel.overallConfidence)}
            size="small"
          />
          <Typography variant="body2" color="text.secondary">
            {intel.analyzedCount} of {intel.attachmentCount} attachment{intel.attachmentCount !== 1 ? 's' : ''} analyzed
          </Typography>
          {intel.latestExtractionMethod && (
            <Chip
              label={METHOD_LABELS[intel.latestExtractionMethod] ?? intel.latestExtractionMethod}
              size="small"
              variant="outlined"
            />
          )}
          <Box sx={{ ml: 'auto' }}>
            <Button
              variant="outlined"
              size="small"
              startIcon={analyzeMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <AnalyticsIcon />}
              disabled={analyzeMutation.isPending}
              onClick={() => analyzeMutation.mutate()}
            >
              {analyzeMutation.isPending ? 'Requesting...' : 'Re-analyze with AI'}
            </Button>
          </Box>
        </Box>
      </Paper>

      {/* Intel Summary Cards */}
      {hasAnyIntel ? (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {intelFields.map(
            (field) =>
              field.value && (
                <Grid key={field.label} size={{ xs: 12, sm: 6, md: 4 }}>
                  <IntelCard label={field.label} fieldName={field.fieldName} value={field.value} sources={sources} />
                </Grid>
              ),
          )}
          {intel.laborCategories.length > 0 && (
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <ListCard label="Labor Categories" fieldName="labor_categories" items={intel.laborCategories} sources={sources} />
            </Grid>
          )}
          {intel.keyRequirements.length > 0 && (
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <ListCard label="Key Requirements" fieldName="key_requirements" items={intel.keyRequirements} sources={sources} />
            </Grid>
          )}
        </Grid>
      ) : (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <EmptyState
            title="No Extracted Intelligence"
            message="Attachments have been cataloged but no intelligence fields were extracted yet. Try analyzing with AI."
          />
        </Paper>
      )}

      {/* Attachments Table */}
      <AttachmentsTable attachments={intel.attachments ?? []} />
    </Box>
  );
}
