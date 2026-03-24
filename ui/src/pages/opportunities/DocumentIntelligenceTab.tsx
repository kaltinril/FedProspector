import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import DescriptionIcon from '@mui/icons-material/Description';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { getDocumentIntelligence, getAnalysisEstimate, requestAnalysis } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import type {
  DocumentIntelligenceDto,
  IntelSourceDto,
  MergedSourcePassageDto,
  AttachmentSummaryDto,
  AttachmentIntelBreakdownDto,
  AnalysisEstimateDto,
} from '@/types/api';

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

/** Map from fieldName (DB column) to the confidenceDetails key */
const FIELD_CONFIDENCE_KEY: Record<string, string> = {
  clearance_level: 'clearance',
  eval_method: 'evaluation',
  vehicle_type: 'vehicle',
  is_recompete: 'recompete',
  scope_summary: 'scope',
  period_of_performance: 'period',
  pricing_structure: 'pricing',
  place_of_performance: 'place_of_performance',
  labor_categories: 'labor',
  key_requirements: 'requirements',
};

/** Map from fieldName to the detail text property on DocumentIntelligenceDto */
const FIELD_DETAIL_KEY: Record<string, keyof DocumentIntelligenceDto> = {
  clearance_level: 'clearanceDetails',
  eval_method: 'evalDetails',
  vehicle_type: 'vehicleDetails',
  is_recompete: 'recompeteDetails',
  pricing_structure: 'pricingDetails',
  place_of_performance: 'popDetails',
};

function formatFileSize(bytes: number | undefined | null): string {
  if (bytes == null) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}K` : `${n}`;
}

// ---------------------------------------------------------------------------
// Renders a merged passage from the API — one text block with multiple highlights
// ---------------------------------------------------------------------------

function MergedSourceBlock({ passage }: { passage: MergedSourcePassageDto }) {
  // Merge overlapping/nested highlights into non-overlapping spans.
  // e.g. "TOP SECRET" (0-10) + "SECRET" (4-10) → single span (0-10)
  const merged: { start: number; end: number }[] = [];
  for (const h of passage.highlights) {
    if (merged.length > 0 && h.start <= merged[merged.length - 1].end) {
      // Overlapping or adjacent — extend the previous span
      merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, h.end);
    } else {
      merged.push({ start: h.start, end: h.end });
    }
  }

  // Build text fragments: alternating plain text and highlighted spans
  const fragments: React.ReactNode[] = [];
  let cursor = 0;

  for (const h of merged) {
    if (h.start > cursor) {
      fragments.push(passage.text.slice(cursor, h.start));
    }
    fragments.push(
      <Box key={h.start} component="mark" sx={{ bgcolor: 'warning.light', color: 'warning.contrastText', px: 0.25, borderRadius: 0.5 }}>
        {passage.text.slice(h.start, h.end)}
      </Box>,
    );
    cursor = h.end;
  }
  if (cursor < passage.text.length) {
    fragments.push(passage.text.slice(cursor));
  }

  return (
    <Box sx={{ mt: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5, flexWrap: 'wrap' }}>
        {passage.methods.map((m) => (
          <Chip
            key={m}
            label={METHOD_LABELS[m] ?? m}
            size="small"
            variant="outlined"
            sx={{ fontSize: '0.6rem', height: 18 }}
          />
        ))}
        {(() => {
          const rank: Record<string, number> = { high: 3, medium: 2, low: 1 };
          const best = passage.confidences.sort((a, b) => (rank[b] ?? 0) - (rank[a] ?? 0))[0];
          return best ? (
            <Chip
              label={best}
              size="small"
              color={getConfidenceColor(best)}
              sx={{ fontSize: '0.6rem', height: 18 }}
            />
          ) : null;
        })()}
        {passage.highlights.length > 1 && (
          <Typography variant="caption" color="text.secondary">
            {passage.highlights.length} matches
          </Typography>
        )}
      </Box>
      <Typography variant="caption" color="text.secondary" display="block">
        {passage.filename}
        {passage.pageNumber != null ? `, p.${passage.pageNumber}` : ''}
      </Typography>
      <Typography
        variant="body2"
        sx={{ mt: 0.5, fontFamily: 'monospace', fontSize: '0.75rem' }}
      >
        {fragments}
      </Typography>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// AI Source Item — renders an AI explanation (no merging needed)
// ---------------------------------------------------------------------------

function AISourceItem({ src }: { src: IntelSourceDto }) {
  return (
    <Box sx={{ mt: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
        <Chip
          label={METHOD_LABELS[src.extractionMethod] ?? src.extractionMethod}
          size="small"
          variant="outlined"
          sx={{ fontSize: '0.6rem', height: 18 }}
        />
        {src.confidence && (
          <Chip
            label={src.confidence}
            size="small"
            color={getConfidenceColor(src.confidence)}
            sx={{ fontSize: '0.6rem', height: 18 }}
          />
        )}
      </Box>
      {src.sourceFilename && (
        <Typography variant="caption" color="text.secondary" display="block">
          {src.sourceFilename}
        </Typography>
      )}
      {src.matchedText && (
        <Typography variant="body2" sx={{ mt: 0.5, fontSize: '0.8rem', fontStyle: 'italic' }}>
          {src.matchedText}
        </Typography>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Intel Card (one extracted field with provenance + detail text)
// ---------------------------------------------------------------------------

interface IntelCardProps {
  label: string;
  fieldName: string;
  value: string | null | undefined;
  sources: IntelSourceDto[];
  intel: DocumentIntelligenceDto;
}

function IntelCard({ label, fieldName, value, sources, intel }: IntelCardProps) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [detailExpanded, setDetailExpanded] = useState(false);
  if (!value) return null;

  const fieldSources = sources.filter((s) => s.fieldName === fieldName);

  // Use per-field confidence from confidenceDetails, falling back to overallConfidence
  const confidenceKey = FIELD_CONFIDENCE_KEY[fieldName];
  const confidence = (confidenceKey && intel.confidenceDetails?.[confidenceKey])
    ?? intel.overallConfidence
    ?? 'unknown';

  // Get distinct methods from sources for this field
  const fieldMethods = [...new Set(fieldSources.map((s) => s.extractionMethod).filter(Boolean))];

  // Detail text from AI analysis
  const detailKey = FIELD_DETAIL_KEY[fieldName];
  const detailText = detailKey ? (intel[detailKey] as string | undefined) : undefined;

  return (
    <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0 }}>
            {fieldMethods.map((m) => (
              <Chip
                key={m}
                label={METHOD_LABELS[m] ?? m}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.65rem', height: 20 }}
              />
            ))}
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

      {/* AI Analysis detail text (expandable) */}
      {detailText && (
        <Box sx={{ px: 2, pb: 0.5 }}>
          <Box
            sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
            onClick={() => setDetailExpanded((prev) => !prev)}
          >
            <Typography variant="caption" color="text.secondary">
              AI Analysis
            </Typography>
            <IconButton size="small" sx={{ ml: 'auto', transform: detailExpanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
              <ExpandMoreIcon fontSize="small" />
            </IconButton>
          </Box>
          <Collapse in={detailExpanded}>
            <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1, mb: 1 }}>
              <Typography variant="body2" color="text.primary" sx={{ whiteSpace: 'pre-wrap' }}>
                {detailText}
              </Typography>
            </Box>
          </Collapse>
        </Box>
      )}

      {/* Source provenance (expandable, merged from API) */}
      {(() => {
        const fieldPassages = (intel.mergedPassages ?? []).filter(p => p.fieldName === fieldName);
        const aiSrcs = fieldSources.filter(s => s.extractionMethod?.startsWith('ai_'));
        const totalPassages = fieldPassages.length + aiSrcs.length;
        const totalMatches = fieldPassages.reduce((sum, p) => sum + p.matchCount, 0) + aiSrcs.length;
        if (totalPassages === 0) return null;
        return (
          <Box sx={{ px: 2, pb: 1 }}>
            <Box
              sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
              onClick={() => setSourcesExpanded((prev) => !prev)}
            >
              <Typography variant="caption" color="text.secondary">
                View Sources ({totalPassages}{totalMatches !== totalPassages ? ` from ${totalMatches} matches` : ''})
              </Typography>
              <IconButton size="small" sx={{ ml: 'auto', transform: sourcesExpanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
                <ExpandMoreIcon fontSize="small" />
              </IconButton>
            </Box>
            <Collapse in={sourcesExpanded}>
              {aiSrcs.map((src, idx) => (
                <AISourceItem key={`ai-${idx}`} src={src} />
              ))}
              {fieldPassages.map((passage, idx) => (
                <MergedSourceBlock key={`kw-${idx}`} passage={passage} />
              ))}
            </Collapse>
          </Box>
        );
      })()}
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
  intel: DocumentIntelligenceDto;
}

const LIST_CARD_COLLAPSED_LIMIT = 5;

function ListCard({ label, fieldName, items, sources, intel }: ListCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [showAll, setShowAll] = useState(false);
  if (items.length === 0) return null;

  const fieldSources = sources.filter((s) => s.fieldName === fieldName);

  // Use per-field confidence from confidenceDetails, falling back to overallConfidence
  const confidenceKey = FIELD_CONFIDENCE_KEY[fieldName];
  const confidence = (confidenceKey && intel.confidenceDetails?.[confidenceKey])
    ?? intel.overallConfidence
    ?? 'unknown';

  const needsCollapse = items.length > LIST_CARD_COLLAPSED_LIMIT;
  const visibleItems = needsCollapse && !showAll ? items.slice(0, LIST_CARD_COLLAPSED_LIMIT) : items;

  return (
    <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {label} ({items.length})
          </Typography>
          <Chip
            label={confidence}
            size="small"
            color={getConfidenceColor(confidence)}
            sx={{ fontSize: '0.65rem', height: 20 }}
          />
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {visibleItems.map((item, idx) => (
            <Chip key={idx} label={item} size="small" variant="outlined" />
          ))}
        </Box>
        {needsCollapse && (
          <Button
            size="small"
            onClick={() => setShowAll((prev) => !prev)}
            sx={{ mt: 1, textTransform: 'none', fontSize: '0.75rem' }}
          >
            {showAll ? 'Show fewer' : `Show all ${items.length} items`}
          </Button>
        )}
      </CardContent>

      {(() => {
        const fieldPassages = (intel.mergedPassages ?? []).filter(p => p.fieldName === fieldName);
        const aiSrcs = fieldSources.filter(s => s.extractionMethod?.startsWith('ai_'));
        const totalPassages = fieldPassages.length + aiSrcs.length;
        const totalMatches = fieldPassages.reduce((sum, p) => sum + p.matchCount, 0) + aiSrcs.length;
        if (totalPassages === 0) return null;
        return (
          <Box sx={{ px: 2, pb: 1 }}>
            <Box
              sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
              onClick={() => setExpanded((prev) => !prev)}
            >
              <Typography variant="caption" color="text.secondary">
                View Sources ({totalPassages}{totalMatches !== totalPassages ? ` from ${totalMatches} matches` : ''})
              </Typography>
              <IconButton size="small" sx={{ ml: 'auto', transform: expanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
                <ExpandMoreIcon fontSize="small" />
              </IconButton>
            </Box>
            <Collapse in={expanded}>
              {aiSrcs.map((src, idx) => (
                <AISourceItem key={`ai-${idx}`} src={src} />
              ))}
              {fieldPassages.map((passage, idx) => (
                <MergedSourceBlock key={`kw-${idx}`} passage={passage} />
              ))}
            </Collapse>
          </Box>
        );
      })()}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Per-Attachment Breakdown Section
// ---------------------------------------------------------------------------

function PerAttachmentBreakdown({ items }: { items: AttachmentIntelBreakdownDto[] }) {
  const [expanded, setExpanded] = useState(false);
  if (items.length === 0) return null;

  // Collect non-null field labels for a breakdown item
  const getFieldChips = (item: AttachmentIntelBreakdownDto) => {
    const chips: { label: string; value: string }[] = [];
    if (item.clearanceRequired) chips.push({ label: 'Clearance', value: item.clearanceRequired + (item.clearanceLevel ? ` / ${item.clearanceLevel}` : '') });
    if (item.evalMethod) chips.push({ label: 'Eval', value: item.evalMethod });
    if (item.vehicleType) chips.push({ label: 'Vehicle', value: item.vehicleType });
    if (item.isRecompete) chips.push({ label: 'Recompete', value: item.isRecompete });
    if (item.incumbentName) chips.push({ label: 'Incumbent', value: item.incumbentName });
    if (item.pricingStructure) chips.push({ label: 'Pricing', value: item.pricingStructure });
    if (item.placeOfPerformance) chips.push({ label: 'PoP', value: item.placeOfPerformance });
    return chips;
  };

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
      <Box
        sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setExpanded((prev) => !prev)}
      >
        <Typography variant="subtitle2">
          Per-Attachment Breakdown ({items.length} attachment{items.length !== 1 ? 's' : ''})
        </Typography>
        <IconButton size="small" sx={{ ml: 'auto', transform: expanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ mt: 2 }}>
          {items.map((item) => {
            const chips = getFieldChips(item);
            return (
              <Box
                key={item.attachmentId}
                sx={{ p: 1.5, mb: 1, bgcolor: 'action.hover', borderRadius: 1 }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: chips.length > 0 ? 1 : 0 }}>
                  <DescriptionIcon fontSize="small" color="action" />
                  <Typography variant="body2" sx={{ fontWeight: 600, wordBreak: 'break-word' }}>
                    {item.filename}
                  </Typography>
                  <Chip
                    label={METHOD_LABELS[item.extractionMethod] ?? item.extractionMethod}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: '0.6rem', height: 18 }}
                  />
                  {item.confidence && (
                    <Chip
                      label={item.confidence}
                      size="small"
                      color={getConfidenceColor(item.confidence)}
                      sx={{ fontSize: '0.6rem', height: 18 }}
                    />
                  )}
                </Box>
                {chips.length > 0 && (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, ml: 4 }}>
                    {chips.map((c) => (
                      <Chip
                        key={c.label}
                        label={`${c.label}: ${c.value}`}
                        size="small"
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                    ))}
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>
      </Collapse>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Attachment Status Chip
// ---------------------------------------------------------------------------

const DOWNLOAD_STATUS_COLOR: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  downloaded: 'success',
  pending: 'warning',
  failed: 'error',
  skipped: 'default',
};

const EXTRACTION_STATUS_COLOR: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  extracted: 'success',
  analyzed: 'success',
  pending: 'warning',
  failed: 'error',
  skipped: 'default',
};

// ---------------------------------------------------------------------------
// Attachments Table — with clickable filenames (Problem 4)
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
            {attachments.map((att) => {
              const isGone = att.downloadStatus === 'skipped' && !!att.skipReason;
              const skipLabel = att.skipReason
                ? att.skipReason.replace(/_/g, ' ').replace(/^http /, 'HTTP ').replace(/^max retries /, 'Max retries: ')
                : undefined;

              return (
                <TableRow key={att.attachmentId} sx={isGone ? { opacity: 0.45 } : undefined}>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <DescriptionIcon fontSize="small" color={isGone ? 'disabled' : 'action'} />
                      {att.url && !isGone ? (
                        <Link
                          href={att.url}
                          target="_blank"
                          rel="noopener"
                          variant="body2"
                          sx={{ wordBreak: 'break-word' }}
                        >
                          {att.filename}
                        </Link>
                      ) : (
                        <Typography variant="body2" sx={{ wordBreak: 'break-word' }} color={isGone ? 'text.disabled' : 'text.primary'}>
                          {att.filename}
                        </Typography>
                      )}
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
                    {isGone ? (
                      <Tooltip title={skipLabel ?? 'Removed upstream'} arrow>
                        <Chip
                          label="removed"
                          size="small"
                          color="default"
                          variant="outlined"
                        />
                      </Tooltip>
                    ) : (
                      <Chip
                        label={att.downloadStatus}
                        size="small"
                        color={DOWNLOAD_STATUS_COLOR[att.downloadStatus.toLowerCase()] ?? 'default'}
                      />
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={att.extractionStatus}
                      size="small"
                      color={EXTRACTION_STATUS_COLOR[att.extractionStatus.toLowerCase()] ?? 'default'}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
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

  const basicAnalysisMutation = useMutation({
    mutationFn: () => requestAnalysis(noticeId, 'basic'),
    onSuccess: () => {
      enqueueSnackbar('Basic analysis requested. Attachments will be downloaded and analyzed.', { variant: 'success' });
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

  // --- AI Analysis Confirmation Dialog ---
  const [estimateDialogOpen, setEstimateDialogOpen] = useState(false);
  const [estimate, setEstimate] = useState<AnalysisEstimateDto | null>(null);
  const [estimateLoading, setEstimateLoading] = useState(false);
  const [estimateError, setEstimateError] = useState(false);

  const handleEnhanceWithAI = async () => {
    setEstimateLoading(true);
    setEstimateError(false);
    setEstimate(null);
    try {
      const result = await getAnalysisEstimate(noticeId);
      setEstimate(result);
      setEstimateDialogOpen(true);
    } catch {
      setEstimateError(true);
      setEstimateDialogOpen(true);
    } finally {
      setEstimateLoading(false);
    }
  };

  const handleConfirmAnalyze = () => {
    setEstimateDialogOpen(false);
    setEstimate(null);
    analyzeMutation.mutate();
  };

  const handleCancelDialog = () => {
    setEstimateDialogOpen(false);
    setEstimate(null);
    setEstimateError(false);
  };

  // --- Confirmation Dialog ---
  const estimateDialog = (
    <Dialog open={estimateDialogOpen} onClose={handleCancelDialog} maxWidth="sm" fullWidth>
      <DialogTitle>Analyze Documents with AI?</DialogTitle>
      <DialogContent>
        {estimateError ? (
          <Typography color="text.secondary">
            Unable to estimate cost. Proceed anyway?
          </Typography>
        ) : estimate && estimate.remainingToAnalyze === 0 ? (
          <>
            <Typography gutterBottom>
              All {estimate.attachmentCount} document{estimate.attachmentCount !== 1 ? 's' : ''} already have AI analysis. Re-analyze?
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Model: Claude {estimate.model}
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, mt: 1 }}>
              Estimated cost: ${estimate.estimatedCostUsd.toFixed(4)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              ~{formatTokens(estimate.estimatedInputTokens)} input tokens, ~{formatTokens(estimate.estimatedOutputTokens)} output tokens
            </Typography>
          </>
        ) : estimate ? (
          <>
            <Typography gutterBottom>
              {estimate.remainingToAnalyze} document{estimate.remainingToAnalyze !== 1 ? 's' : ''} to analyze
              {estimate.alreadyAnalyzed > 0 && (
                <Typography component="span" color="text.secondary">
                  {' '}({estimate.alreadyAnalyzed} already analyzed)
                </Typography>
              )}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Model: Claude {estimate.model}
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, mt: 1 }}>
              Estimated cost: ${estimate.estimatedCostUsd.toFixed(4)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              ~{formatTokens(estimate.estimatedInputTokens)} input tokens, ~{formatTokens(estimate.estimatedOutputTokens)} output tokens
            </Typography>
          </>
        ) : null}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCancelDialog}>Cancel</Button>
        <Button variant="contained" onClick={handleConfirmAnalyze}>
          Analyze
        </Button>
      </DialogActions>
    </Dialog>
  );

  // --- Loading ---
  if (isLoading) {
    return (
      <>
        <LoadingState message="Loading document intelligence..." />
        {estimateDialog}
      </>
    );
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
      <>
        <EmptyState
          title="No Document Intelligence Available"
          message="No document intelligence available yet. Run the daily pipeline or use the CLI to download and analyze attachments for this opportunity."
          icon={<DescriptionIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />}
          action={
            <Button
              variant="contained"
              startIcon={basicAnalysisMutation.isPending ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />}
              disabled={basicAnalysisMutation.isPending}
              onClick={() => basicAnalysisMutation.mutate()}
            >
              {basicAnalysisMutation.isPending ? 'Requesting...' : 'Run Basic Analysis'}
            </Button>
          }
        />
        {estimateDialog}
      </>
    );
  }

  // --- Error ---
  if (isError) {
    return (
      <>
        <ErrorState
          title="Failed to load document intelligence"
          message="An error occurred while loading document intelligence for this opportunity."
        />
        {estimateDialog}
      </>
    );
  }

  // --- State 2: Attachments exist but no intel extracted ---
  const hasAnyIntelData = intel && (
    intel.analyzedCount > 0 ||
    intel.clearanceRequired || intel.clearanceLevel ||
    intel.evalMethod || intel.vehicleType ||
    intel.isRecompete || intel.scopeSummary ||
    intel.periodOfPerformance ||
    (intel.laborCategories?.length ?? 0) > 0 ||
    (intel.keyRequirements?.length ?? 0) > 0
  );

  if (intel && !hasAnyIntelData) {
    return (
      <Box>
        <Paper variant="outlined" sx={{ p: 3, mb: 3, textAlign: 'center' }}>
          <DescriptionIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
          <Typography variant="subtitle1" gutterBottom>
            Attachments Cataloged but Not Yet Analyzed
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {intel.attachmentCount} attachment{intel.attachmentCount !== 1 ? 's' : ''} found. Run analysis to extract intelligence.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
            <Button
              variant="contained"
              startIcon={basicAnalysisMutation.isPending ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />}
              disabled={basicAnalysisMutation.isPending}
              onClick={() => basicAnalysisMutation.mutate()}
            >
              {basicAnalysisMutation.isPending ? 'Requesting...' : 'Run Basic Analysis'}
            </Button>
            <Button
              variant="outlined"
              startIcon={estimateLoading || analyzeMutation.isPending ? <CircularProgress size={18} color="inherit" /> : <AnalyticsIcon />}
              disabled={estimateLoading || analyzeMutation.isPending}
              onClick={handleEnhanceWithAI}
            >
              {estimateLoading ? 'Estimating...' : analyzeMutation.isPending ? 'Requesting...' : 'Enhance with AI'}
            </Button>
          </Box>
        </Paper>
        <AttachmentsTable attachments={intel.attachments ?? []} />
        {estimateDialog}
      </Box>
    );
  }

  // --- Render Data (State 3: Intel extracted) ---
  const sources = intel.sources ?? [];
  const availableMethods = intel.availableMethods ?? [];

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
          {/* Show chips for all available extraction methods */}
          {availableMethods.length > 0 ? (
            availableMethods.map((m) => (
              <Chip
                key={m}
                label={METHOD_LABELS[m] ?? m}
                size="small"
                variant="outlined"
              />
            ))
          ) : intel.latestExtractionMethod ? (
            <Chip
              label={METHOD_LABELS[intel.latestExtractionMethod] ?? intel.latestExtractionMethod}
              size="small"
              variant="outlined"
            />
          ) : null}
          <Box sx={{ ml: 'auto' }}>
            <Button
              variant="outlined"
              size="small"
              startIcon={estimateLoading || analyzeMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <AnalyticsIcon />}
              disabled={estimateLoading || analyzeMutation.isPending}
              onClick={handleEnhanceWithAI}
            >
              {estimateLoading
                ? 'Estimating...'
                : analyzeMutation.isPending
                  ? 'Requesting...'
                  : intel.latestExtractionMethod === 'keyword'
                    ? 'Enhance with AI'
                    : 'Re-analyze'}
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
                  <IntelCard label={field.label} fieldName={field.fieldName} value={field.value} sources={sources} intel={intel} />
                </Grid>
              ),
          )}
          {intel.laborCategories.length > 0 && (
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <ListCard label="Labor Categories" fieldName="labor_categories" items={intel.laborCategories} sources={sources} intel={intel} />
            </Grid>
          )}
          {intel.keyRequirements.length > 0 && (
            <Grid size={{ xs: 12 }}>
              <ListCard label="Key Requirements" fieldName="key_requirements" items={intel.keyRequirements} sources={sources} intel={intel} />
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

      {/* Per-Attachment Breakdown (Problem 7) */}
      {intel.perAttachmentIntel && intel.perAttachmentIntel.length > 0 && (
        <PerAttachmentBreakdown items={intel.perAttachmentIntel} />
      )}

      {/* Attachments Table */}
      <AttachmentsTable attachments={intel.attachments ?? []} />
      {estimateDialog}
    </Box>
  );
}
