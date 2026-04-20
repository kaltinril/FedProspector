import { useState, useEffect } from 'react';
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
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import DescriptionIcon from '@mui/icons-material/Description';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import SummarizeIcon from '@mui/icons-material/Summarize';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { getDocumentIntelligence, getAnalysisEstimate, requestAnalysis, getAnalysisStatus, requestAttachmentAnalysis, getAttachmentAnalysisStatus } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import type {
  DocumentIntelligenceDto,
  MethodIntelDto,
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

/** Keys of MethodIntelDto whose value type is `string | undefined`. */
type MethodIntelStringKey = NonNullable<{
  [K in keyof MethodIntelDto]: MethodIntelDto[K] extends string | undefined ? K : never;
}[keyof MethodIntelDto]>;

const getMethodFieldValue = (
  methodIntel: MethodIntelDto,
  fieldKey: MethodIntelStringKey,
): string | undefined => {
  return methodIntel[fieldKey];
};

// ---------------------------------------------------------------------------
// Scope Summary Card — prominent display of AI scope summary
// ---------------------------------------------------------------------------

function ScopeSummaryCard({ summary, methods }: { summary: string; methods: string[] }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: expanded ? 1 : 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SummarizeIcon color="primary" fontSize="small" />
          <Typography variant="subtitle2">Scope Summary</Typography>
          {methods.filter(m => m !== 'keyword').map(m => (
            <Chip key={m} label={METHOD_LABELS[m] || m} size="small" variant="outlined" sx={{ fontSize: '0.65rem', height: 20 }} />
          ))}
        </Box>
        <IconButton size="small" onClick={() => setExpanded(!expanded)}>
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Typography
          variant="body2"
          sx={{
            color: "text.secondary",
            whiteSpace: 'pre-line'
          }}>
          {summary}
        </Typography>
      </Collapse>
    </Paper>
  );
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
          <Typography variant="caption" sx={{
            color: "text.secondary"
          }}>
            {passage.highlights.length} matches
          </Typography>
        )}
      </Box>
      <Typography
        variant="caption"
        sx={{
          color: "text.secondary",
          display: "block"
        }}>
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
        <Typography
          variant="caption"
          sx={{
            color: "text.secondary",
            display: "block"
          }}>
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
  fieldKey?: MethodIntelStringKey;
  value: string | null | undefined;
  sources: IntelSourceDto[];
  intel: DocumentIntelligenceDto;
}

function IntelCard({ label, fieldName, fieldKey, value, sources, intel }: IntelCardProps) {
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
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1, mb: 1 }}>
          <Typography
            variant="caption"
            sx={{
              color: "text.secondary",
              flexShrink: 0
            }}>
            {label}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'nowrap', justifyContent: 'flex-end', overflow: 'hidden', minWidth: 0 }}>
            {/* Per-method values inline — only show values when methods disagree */}
            {fieldKey && intel.methodBreakdown && Object.keys(intel.methodBreakdown).length > 1
              ? (() => {
                  const entries = Object.entries(intel.methodBreakdown);
                  const vals = entries.map(([, d]) => getMethodFieldValue(d, fieldKey)).filter(Boolean);
                  const allAgree = vals.length > 1 && vals.every(v => v === vals[0]);
                  if (allAgree) {
                    return entries.map(([method]) => (
                      <Chip key={method} label={METHOD_LABELS[method] || method} size="small" variant="outlined" sx={{ fontSize: '0.6rem', height: 18 }} />
                    ));
                  }
                  return entries.map(([method, methodData]) => {
                    const methodValue = getMethodFieldValue(methodData, fieldKey);
                    return (
                      <Tooltip key={method} title={methodValue || ''}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0, flexShrink: 1 }}>
                          <Chip label={METHOD_LABELS[method] || method} size="small" variant="outlined" sx={{ fontSize: '0.6rem', height: 18, flexShrink: 0 }} />
                          <Typography
                            variant="caption"
                            noWrap
                            sx={{
                              color: "text.secondary",
                              maxWidth: 120
                            }}>
                            {methodValue || '\u2014'}
                          </Typography>
                        </Box>
                      </Tooltip>
                    );
                  });
                })()
              : fieldMethods.map((m) => (
                  <Chip
                    key={m}
                    label={METHOD_LABELS[m] ?? m}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: '0.65rem', height: 20 }}
                  />
                ))
            }
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
            <Typography variant="caption" sx={{
              color: "text.secondary"
            }}>
              AI Analysis
            </Typography>
            <IconButton size="small" sx={{ ml: 'auto', transform: detailExpanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
              <ExpandMoreIcon fontSize="small" />
            </IconButton>
          </Box>
          <Collapse in={detailExpanded}>
            <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1, mb: 1 }}>
              <Typography
                variant="body2"
                sx={{
                  color: "text.primary",
                  whiteSpace: 'pre-wrap'
                }}>
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
              <Typography variant="caption" sx={{
                color: "text.secondary"
              }}>
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
          <Typography variant="caption" sx={{
            color: "text.secondary"
          }}>
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
              <Typography variant="caption" sx={{
                color: "text.secondary"
              }}>
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

  // Group by filename
  const groups = items.reduce((acc, item) => {
    const key = item.filename;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {} as Record<string, AttachmentIntelBreakdownDto[]>);

  const fileCount = Object.keys(groups).length;

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
      <Box
        sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setExpanded((prev) => !prev)}
      >
        <Typography variant="subtitle2">
          Per-Attachment Breakdown ({fileCount} file{fileCount !== 1 ? 's' : ''}, {items.length} result{items.length !== 1 ? 's' : ''})
        </Typography>
        <IconButton size="small" sx={{ ml: 'auto', transform: expanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ mt: 2 }}>
          {Object.entries(groups).map(([filename, groupItems]) => (
            <Box key={filename} sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <DescriptionIcon fontSize="small" color="action" />
                <Typography variant="body2" sx={{ fontWeight: 600, wordBreak: 'break-word' }}>
                  {filename}
                </Typography>
              </Box>
              {groupItems.map((item, idx) => {
                const chips = getFieldChips(item);
                const scopeText = item.scopeSummary
                  ? item.scopeSummary.length > 200 ? item.scopeSummary.slice(0, 200) + '...' : item.scopeSummary
                  : undefined;
                return (
                  <Box
                    key={`${item.attachmentId}-${item.extractionMethod}-${idx}`}
                    sx={{ p: 1.5, mb: 0.5, ml: 4, bgcolor: 'action.hover', borderRadius: 1 }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: chips.length > 0 || scopeText ? 1 : 0 }}>
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
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
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
                    {scopeText && (
                      <Typography
                        variant="caption"
                        sx={{
                          color: "text.secondary",
                          display: 'block',
                          mt: 0.5,
                          fontStyle: 'italic'
                        }}>
                        {scopeText}
                      </Typography>
                    )}
                  </Box>
                );
              })}
            </Box>
          ))}
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
// Attachment Analysis Poller — invisible component that polls for status
// ---------------------------------------------------------------------------

function AttachmentAnalysisPoller({
  noticeId,
  attachmentId,
  tier,
  onComplete,
  onFailed,
}: {
  noticeId: string;
  attachmentId: number;
  tier: string;
  onComplete: (resultSummary?: string | null) => void;
  onFailed: (msg?: string) => void;
}) {
  const { data: status } = useQuery({
    queryKey: ['attachment-analysis-status', attachmentId, tier],
    queryFn: () => getAttachmentAnalysisStatus(noticeId, attachmentId),
    refetchInterval: 4000,
  });

  useEffect(() => {
    if (!status?.status) return;
    if (status.status === 'COMPLETED') onComplete(status.resultSummary);
    else if (status.status === 'FAILED') onFailed(status.errorMessage ?? undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.status]);

  return null;
}

// ---------------------------------------------------------------------------
// Attachments Table — with clickable filenames and per-attachment analysis
// ---------------------------------------------------------------------------

function AttachmentsTable({ attachments, noticeId }: { attachments: AttachmentSummaryDto[]; noticeId: string }) {
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();
  const [pendingAnalysis, setPendingAnalysis] = useState<Map<string, number>>(new Map());

  if (attachments.length === 0) return null;

  const handleAnalyze = async (attachmentId: number, tier: string) => {
    const key = `${attachmentId}-${tier}`;
    try {
      const result = await requestAttachmentAnalysis(noticeId, attachmentId, tier);
      if (result.requestId != null) {
        setPendingAnalysis((prev) => new Map(prev).set(key, result.requestId!));
      }
    } catch {
      enqueueSnackbar(`Failed to request ${tier} analysis`, { variant: 'error' });
    }
  };

  const handleComplete = (attachmentId: number, tier: string, resultSummary?: string | null) => {
    const key = `${attachmentId}-${tier}`;
    setPendingAnalysis((prev) => {
      const next = new Map(prev);
      next.delete(key);
      return next;
    });
    const label = tier === 'keyword' ? 'Keyword' : tier === 'redownload' ? 'Re-download' : tier === 'reextract' ? 'Re-extract' : 'AI';
    let found = true;
    if (resultSummary) {
      try {
        const summary = JSON.parse(resultSummary);
        const extracted = summary.extracted ?? summary.analyzed ?? 0;
        found = extracted > 0;
      } catch { /* ignore parse errors */ }
    }
    enqueueSnackbar(
      found ? `${label} analysis complete.` : `${label} analysis ran but found no results for this attachment.`,
      { variant: found ? 'success' : 'info' },
    );
    queryClient.invalidateQueries({
      queryKey: queryKeys.opportunities.documentIntelligence(noticeId),
    });
  };

  const handleFailed = (attachmentId: number, tier: string, msg?: string) => {
    const key = `${attachmentId}-${tier}`;
    setPendingAnalysis((prev) => {
      const next = new Map(prev);
      next.delete(key);
      return next;
    });
    const failLabel = tier === 'keyword' ? 'Keyword' : tier === 'redownload' ? 'Re-download' : tier === 'reextract' ? 'Re-extract' : 'AI';
    enqueueSnackbar(`${failLabel} failed${msg ? `: ${msg}` : ''}`, { variant: 'error' });
  };

  const renderAnalysisCell = (att: AttachmentSummaryDto, tier: string) => {
    const isGone = att.downloadStatus === 'skipped' && !!att.skipReason;
    const key = `${att.attachmentId}-${tier}`;
    const isPending = pendingAnalysis.has(key);

    if (isGone || att.extractionStatus.toLowerCase() !== 'extracted') {
      return (
        <Typography variant="body2" sx={{
          color: "text.disabled"
        }}>&mdash;</Typography>
      );
    }

    if (isPending) {
      return <CircularProgress size={16} />;
    }

    const wasAnalyzed = tier === 'keyword' ? att.keywordAnalyzedAt : att.aiAnalyzedAt;
    const fieldCount = tier === 'keyword' ? att.keywordFieldCount : att.aiFieldCount;
    if (!wasAnalyzed) {
      return (
        <Chip
          label="analyze"
          size="small"
          variant="outlined"
          onClick={() => handleAnalyze(att.attachmentId, tier)}
          deleteIcon={<RefreshIcon />}
          onDelete={() => handleAnalyze(att.attachmentId, tier)}
        />
      );
    }
    const hasResults = fieldCount > 0;
    const tooltip = hasResults
      ? `${fieldCount} of 12 fields found on ${new Date(wasAnalyzed).toLocaleString()}`
      : `No results found on ${new Date(wasAnalyzed).toLocaleString()}`;
    return (
      <Tooltip title={tooltip}>
        <Chip
          label={hasResults ? `✓ ${fieldCount}` : '-'}
          size="small"
          color={hasResults ? 'success' : 'default'}
          variant={hasResults ? 'filled' : 'outlined'}
          deleteIcon={<RefreshIcon />}
          onDelete={() => handleAnalyze(att.attachmentId, tier)}
        />
      </Tooltip>
    );
  };

  return (
    <>
      {/* Invisible pollers for pending analyses */}
      {Array.from(pendingAnalysis.entries()).map(([key]) => {
        const dashIdx = key.indexOf('-');
        const idStr = key.slice(0, dashIdx);
        const tier = key.slice(dashIdx + 1);
        const attachmentId = Number(idStr);
        return (
          <AttachmentAnalysisPoller
            key={key}
            noticeId={noticeId}
            attachmentId={attachmentId}
            tier={tier}
            onComplete={(rs) => handleComplete(attachmentId, tier, rs)}
            onFailed={(msg) => handleFailed(attachmentId, tier, msg)}
          />
        );
      })}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Attachments ({attachments.length})
        </Typography>
        <TableContainer sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ minWidth: 760 }}>
            <TableHead>
              <TableRow>
                <TableCell>Filename</TableCell>
                <TableCell align="right">Size</TableCell>
                <TableCell align="right">Pages</TableCell>
                <TableCell>Download</TableCell>
                <TableCell>Extraction</TableCell>
                <TableCell>Keyword</TableCell>
                <TableCell>AI</TableCell>
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
                        <Tooltip title={att.downloadedAt ? `Downloaded: ${new Date(att.downloadedAt).toLocaleString()}` : ''}>
                          <Chip
                            label={att.downloadStatus}
                            size="small"
                            color={DOWNLOAD_STATUS_COLOR[att.downloadStatus.toLowerCase()] ?? 'default'}
                            {...(att.downloadStatus === 'downloaded' ? {
                              deleteIcon: <DownloadIcon />,
                              onDelete: () => handleAnalyze(att.attachmentId, 'redownload'),
                            } : {})}
                          />
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>
                      <Tooltip title={att.extractedAt ? `Extracted: ${new Date(att.extractedAt).toLocaleString()}` : ''}>
                        <Chip
                          label={att.extractionStatus}
                          size="small"
                          color={EXTRACTION_STATUS_COLOR[att.extractionStatus.toLowerCase()] ?? 'default'}
                          {...((att.extractionStatus === 'extracted' || att.extractionStatus === 'failed') ? {
                            deleteIcon: <RefreshIcon />,
                            onDelete: () => handleAnalyze(att.attachmentId, 'reextract'),
                          } : {})}
                        />
                      </Tooltip>
                    </TableCell>
                    <TableCell>{renderAnalysisCell(att, 'keyword')}</TableCell>
                    <TableCell>{renderAnalysisCell(att, 'ai')}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main Tab Component
// ---------------------------------------------------------------------------

export default function DocumentIntelligenceTab({ noticeId }: { noticeId: string }) {
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();
  const [analysisRequestId, setAnalysisRequestId] = useState<number | null>(null);

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

  // Poll analysis status while a request is in progress
  const { data: analysisStatus } = useQuery({
    queryKey: queryKeys.opportunities.analysisStatus(noticeId),
    queryFn: () => getAnalysisStatus(noticeId),
    enabled: analysisRequestId != null,
    refetchInterval: 4000,
  });

  // When analysis completes or fails, refresh intel data and stop polling
  useEffect(() => {
    if (analysisRequestId == null || !analysisStatus?.status) return;

    if (analysisStatus.status === 'COMPLETED') {
      setAnalysisRequestId(null);
      enqueueSnackbar('Analysis complete. Results updated.', { variant: 'success' });
      queryClient.invalidateQueries({
        queryKey: queryKeys.opportunities.documentIntelligence(noticeId),
      });
    } else if (analysisStatus.status === 'FAILED') {
      setAnalysisRequestId(null);
      enqueueSnackbar(
        `Analysis failed: ${analysisStatus.errorMessage ?? 'Unknown error'}`,
        { variant: 'error' },
      );
    }
  }, [analysisStatus?.status, analysisStatus?.errorMessage, analysisRequestId, noticeId, queryClient, enqueueSnackbar]);

  const analysisProcessing = analysisRequestId != null;

  const analyzeMutation = useMutation({
    mutationFn: () => requestAnalysis(noticeId, 'haiku'),
    onSuccess: (result) => {
      enqueueSnackbar('Analysis requested. Results will appear after processing.', { variant: 'success' });
      setAnalysisRequestId(result.requestId ?? null);
    },
    onError: () => {
      enqueueSnackbar('Failed to request analysis', { variant: 'error' });
    },
  });

  const basicAnalysisMutation = useMutation({
    mutationFn: () => requestAnalysis(noticeId, 'keyword'),
    onSuccess: (result) => {
      enqueueSnackbar('Keyword extraction requested.', { variant: 'success' });
      setAnalysisRequestId(result.requestId ?? null);
    },
    onError: () => {
      enqueueSnackbar('Failed to request analysis', { variant: 'error' });
    },
  });

  const redownloadMutation = useMutation({
    mutationFn: () => requestAnalysis(noticeId, 'redownload'),
    onSuccess: (result) => {
      enqueueSnackbar('Attachment re-download requested.', { variant: 'success' });
      setAnalysisRequestId(result.requestId ?? null);
    },
    onError: () => {
      enqueueSnackbar('Failed to request re-download', { variant: 'error' });
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
          <Typography sx={{
            color: "text.secondary"
          }}>
            Unable to estimate cost. Proceed anyway?
          </Typography>
        ) : estimate && estimate.remainingToAnalyze === 0 ? (
          <>
            <Typography gutterBottom>
              All {estimate.attachmentCount} document{estimate.attachmentCount !== 1 ? 's' : ''} already have AI analysis. Re-analyze?
            </Typography>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Model: Claude {estimate.model}
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, mt: 1 }}>
              Estimated cost: ${estimate.estimatedCostUsd.toFixed(4)}
            </Typography>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              ~{formatTokens(estimate.estimatedInputTokens)} input tokens, ~{formatTokens(estimate.estimatedOutputTokens)} output tokens
            </Typography>
          </>
        ) : estimate ? (
          <>
            <Typography gutterBottom>
              {estimate.remainingToAnalyze} document{estimate.remainingToAnalyze !== 1 ? 's' : ''} to analyze
              {estimate.alreadyAnalyzed > 0 && (
                <Typography component="span" sx={{
                  color: "text.secondary"
                }}>
                  {' '}({estimate.alreadyAnalyzed} already analyzed)
                </Typography>
              )}
            </Typography>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Model: Claude {estimate.model}
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, mt: 1 }}>
              Estimated cost: ${estimate.estimatedCostUsd.toFixed(4)}
            </Typography>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
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
              startIcon={basicAnalysisMutation.isPending || analysisProcessing ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />}
              disabled={basicAnalysisMutation.isPending || analysisProcessing}
              onClick={() => basicAnalysisMutation.mutate()}
            >
              {basicAnalysisMutation.isPending ? 'Requesting...' : analysisProcessing ? 'Processing...' : 'Run Basic Analysis'}
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
          <Typography
            variant="body2"
            sx={{
              color: "text.secondary",
              mb: 2
            }}>
            {intel.attachmentCount} attachment{intel.attachmentCount !== 1 ? 's' : ''} found. Run analysis to extract intelligence.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
            <Button
              variant="contained"
              startIcon={basicAnalysisMutation.isPending || analysisProcessing ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />}
              disabled={basicAnalysisMutation.isPending || analysisProcessing}
              onClick={() => basicAnalysisMutation.mutate()}
            >
              {basicAnalysisMutation.isPending ? 'Requesting...' : analysisProcessing ? 'Processing...' : 'Run Basic Analysis'}
            </Button>
            <Button
              variant="outlined"
              startIcon={estimateLoading || analyzeMutation.isPending || analysisProcessing ? <CircularProgress size={18} color="inherit" /> : <AnalyticsIcon />}
              disabled={estimateLoading || analyzeMutation.isPending || analysisProcessing}
              onClick={handleEnhanceWithAI}
            >
              {estimateLoading ? 'Estimating...' : analyzeMutation.isPending ? 'Requesting...' : analysisProcessing ? 'Processing...' : 'Enhance with AI'}
            </Button>
          </Box>
        </Paper>
        <AttachmentsTable attachments={intel.attachments ?? []} noticeId={noticeId} />
        {estimateDialog}
      </Box>
    );
  }

  // --- Render Data (State 3: Intel extracted) ---
  const sources = intel.sources ?? [];
  const availableMethods = intel.availableMethods ?? [];

  // Build intel card entries
  type IntelField = { label: string; fieldName: string; fieldKey?: MethodIntelStringKey; value: string | null | undefined };
  const intelFields: IntelField[] = [
    { label: 'Security Clearance', fieldName: 'clearance_level', fieldKey: 'clearanceLevel', value: [intel.clearanceLevel, intel.clearanceScope].filter(Boolean).join(' - ') || intel.clearanceRequired || null },
    { label: 'Evaluation Method', fieldName: 'eval_method', fieldKey: 'evalMethod', value: intel.evalMethod },
    { label: 'Contract Vehicle', fieldName: 'vehicle_type', fieldKey: 'vehicleType', value: intel.vehicleType },
    {
      label: 'Recompete Status',
      fieldName: 'is_recompete',
      fieldKey: 'isRecompete',
      value: intel.isRecompete != null
        ? `${intel.isRecompete}${intel.incumbentName ? ` (Incumbent: ${intel.incumbentName})` : ''}`
        : null,
    },
    { label: 'Period of Performance', fieldName: 'period_of_performance', fieldKey: 'periodOfPerformance', value: intel.periodOfPerformance },
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
          <Typography variant="body2" sx={{
            color: "text.secondary"
          }}>
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
          <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
            {(() => {
              const anyBusy = redownloadMutation.isPending || basicAnalysisMutation.isPending || estimateLoading || analyzeMutation.isPending || analysisProcessing;
              const aiLabel = availableMethods.some(m => m.startsWith('ai_')) ? 'Re-analyze AI' : 'Enhance with AI';
              return (
                <>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={redownloadMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <DownloadIcon />}
                    disabled={anyBusy}
                    onClick={() => redownloadMutation.mutate()}
                  >
                    {redownloadMutation.isPending ? 'Requesting...' : 'Re-download Attachments'}
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={basicAnalysisMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
                    disabled={anyBusy}
                    onClick={() => basicAnalysisMutation.mutate()}
                  >
                    {basicAnalysisMutation.isPending ? 'Requesting...' : 'Re-extract Keywords'}
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={estimateLoading || analyzeMutation.isPending || analysisProcessing ? <CircularProgress size={16} color="inherit" /> : <AnalyticsIcon />}
                    disabled={anyBusy}
                    onClick={handleEnhanceWithAI}
                  >
                    {estimateLoading ? 'Estimating...' : analyzeMutation.isPending ? 'Requesting...' : analysisProcessing ? 'Processing...' : aiLabel}
                  </Button>
                </>
              );
            })()}
          </Box>
        </Box>
      </Paper>
      {/* Scope Summary — prominent AI-generated summary */}
      {intel.scopeSummary && (
        <ScopeSummaryCard summary={intel.scopeSummary} methods={availableMethods} />
      )}
      {/* Intel Summary Cards */}
      {hasAnyIntel ? (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {intelFields.map(
            (field) =>
              field.value && (
                <Grid key={field.label} size={{ xs: 12, sm: 6, md: 4 }}>
                  <IntelCard label={field.label} fieldName={field.fieldName} fieldKey={field.fieldKey} value={field.value} sources={sources} intel={intel} />
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
      <AttachmentsTable attachments={intel.attachments ?? []} noticeId={noticeId} />
      {estimateDialog}
    </Box>
  );
}
