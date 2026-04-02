import { useCallback, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import AddOutlined from '@mui/icons-material/AddOutlined';
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';

import { PageHeader } from '@/components/shared/PageHeader';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { estimateIgce } from '@/api/pricing';
import { formatCurrency } from '@/utils/formatters';
import type { IgceRequest, IgceResponse, IgceMethodResult } from '@/types/api';

// ---------------------------------------------------------------------------
// Method Card
// ---------------------------------------------------------------------------

function MethodCard({ method }: { method: IgceMethodResult }) {
  const confidencePct = method.confidence * 100;
  let confidenceColor: 'success' | 'warning' | 'error' = 'success';
  if (confidencePct < 50) confidenceColor = 'error';
  else if (confidencePct < 75) confidenceColor = 'warning';

  return (
    <Card variant="outlined" sx={{ flex: 1, minWidth: 280 }}>
      <CardContent>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          {method.methodName}
        </Typography>
        <Typography variant="h5" fontWeight={700} color="primary.main" gutterBottom>
          {formatCurrency(method.estimate)}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Confidence
          </Typography>
          <LinearProgress
            variant="determinate"
            value={confidencePct}
            color={confidenceColor}
            sx={{ flex: 1, height: 6, borderRadius: 1 }}
          />
          <Typography variant="caption" fontWeight={600}>
            {confidencePct.toFixed(0)}%
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          {method.explanation}
        </Typography>
        <Chip
          label={`${method.dataPoints} data points`}
          size="small"
          variant="outlined"
          sx={{ mt: 1 }}
        />
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IgcePage() {
  const [noticeId, setNoticeId] = useState('');
  const [naicsCode, setNaicsCode] = useState('');
  const [agencyName, setAgencyName] = useState('');
  const [popMonths, setPopMonths] = useState('');
  const [laborMix, setLaborMix] = useState<{ canonicalId: number; hours: number }[]>([
    { canonicalId: 0, hours: 0 },
  ]);

  const mutation = useMutation({
    mutationFn: (request: IgceRequest) => estimateIgce(request),
  });

  const result: IgceResponse | undefined = mutation.data;

  const addLaborMixLine = useCallback(() => {
    setLaborMix((prev) => [...prev, { canonicalId: 0, hours: 0 }]);
  }, []);

  const removeLaborMixLine = useCallback((index: number) => {
    setLaborMix((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const updateLaborMix = useCallback(
    (index: number, updates: Partial<{ canonicalId: number; hours: number }>) => {
      setLaborMix((prev) =>
        prev.map((item, i) => (i === index ? { ...item, ...updates } : item)),
      );
    },
    [],
  );

  const handleSubmit = useCallback(() => {
    const request: IgceRequest = {};
    if (noticeId.trim()) {
      request.noticeId = noticeId.trim();
    } else {
      request.naicsCode = naicsCode.trim() || undefined;
      request.agencyName = agencyName.trim() || undefined;
      request.popMonths = popMonths ? Number(popMonths) : undefined;
      const validMix = laborMix.filter((l) => l.canonicalId > 0 && l.hours > 0);
      if (validMix.length > 0) {
        request.laborMix = validMix;
      }
    }
    mutation.mutate(request);
  }, [noticeId, naicsCode, agencyName, popMonths, laborMix, mutation]);

  const canSubmit = noticeId.trim() || naicsCode.trim();

  function confidenceLevelColor(level: string): 'success' | 'warning' | 'error' {
    if (level === 'High') return 'success';
    if (level === 'Medium') return 'warning';
    return 'error';
  }

  return (
    <Box>
      <PageHeader
        title="IGCE Estimator"
        subtitle="Independent Government Cost Estimate based on market data"
      />

      {/* Input form */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Option 1: Auto-populate from opportunity
        </Typography>
        <TextField
          size="small"
          label="Notice ID"
          value={noticeId}
          onChange={(e) => setNoticeId(e.target.value)}
          fullWidth
          sx={{ mb: 2, maxWidth: 400 }}
          helperText="Enter a notice ID to auto-populate from an existing opportunity"
        />

        <Typography variant="subtitle2" gutterBottom>
          Option 2: Manual entry
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
          <TextField
            size="small"
            label="NAICS Code"
            value={naicsCode}
            onChange={(e) => setNaicsCode(e.target.value)}
            sx={{ minWidth: 140 }}
            disabled={!!noticeId.trim()}
          />
          <TextField
            size="small"
            label="Agency"
            value={agencyName}
            onChange={(e) => setAgencyName(e.target.value)}
            sx={{ minWidth: 200 }}
            disabled={!!noticeId.trim()}
          />
          <TextField
            size="small"
            label="POP (months)"
            type="number"
            value={popMonths}
            onChange={(e) => setPopMonths(e.target.value)}
            sx={{ width: 130 }}
            disabled={!!noticeId.trim()}
          />
        </Box>

        {/* Labor mix */}
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Labor Mix (optional)
        </Typography>
        {laborMix.map((line, i) => (
          <Box key={i} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
            <TextField
              size="small"
              label="Category ID"
              type="number"
              value={line.canonicalId || ''}
              onChange={(e) => updateLaborMix(i, { canonicalId: Number(e.target.value) || 0 })}
              sx={{ minWidth: 200 }}
              disabled={!!noticeId.trim()}
            />
            <TextField
              size="small"
              label="Hours"
              type="number"
              value={line.hours || ''}
              onChange={(e) => updateLaborMix(i, { hours: Number(e.target.value) || 0 })}
              sx={{ width: 100 }}
              disabled={!!noticeId.trim()}
            />
            <IconButton
              size="small"
              onClick={() => removeLaborMixLine(i)}
              disabled={laborMix.length <= 1 || !!noticeId.trim()}
            >
              <DeleteOutlined fontSize="small" />
            </IconButton>
          </Box>
        ))}
        <Button
          size="small"
          startIcon={<AddOutlined />}
          onClick={addLaborMixLine}
          disabled={!!noticeId.trim()}
          sx={{ mb: 2 }}
        >
          Add Labor Category
        </Button>

        <Box>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!canSubmit || mutation.isPending}
          >
            Generate IGCE
          </Button>
        </Box>
      </Paper>

      {/* Loading */}
      {mutation.isPending && <LoadingState message="Generating IGCE estimate..." />}

      {/* Error */}
      {mutation.isError && (
        <ErrorState
          title="IGCE generation failed"
          message="Could not generate cost estimate. Please check inputs and try again."
          onRetry={handleSubmit}
        />
      )}

      {/* Results */}
      {result && (
        <Box>
          {/* Weighted estimate highlight */}
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              mb: 3,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 2,
            }}
          >
            <Box>
              <Typography variant="body2" color="text.secondary">
                Weighted Estimate
              </Typography>
              <Typography variant="h4" fontWeight={700} color="primary.main">
                {formatCurrency(result.weightedEstimate)}
              </Typography>
            </Box>
            <Chip
              label={`Data Quality: ${result.confidenceLevel}`}
              color={confidenceLevelColor(result.confidenceLevel)}
              variant="outlined"
              size="medium"
            />
          </Paper>

          {/* Method cards 2x2 grid */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
              gap: 2,
            }}
          >
            {result.methods.map((method) => (
              <MethodCard key={method.methodName} method={method} />
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}
