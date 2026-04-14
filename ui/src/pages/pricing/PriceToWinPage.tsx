import { useCallback, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { GridColDef } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Alert from '@mui/material/Alert';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { estimatePriceToWin } from '@/api/pricing';
import { formatCurrency } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import type { PriceToWinRequest, PriceToWinResponse, ComparableAward } from '@/types/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SET_ASIDE_OPTIONS = [
  { value: '', label: 'Any' },
  { value: 'WOSB', label: 'WOSB' },
  { value: '8(a)', label: '8(a)' },
  { value: 'HUBZone', label: 'HUBZone' },
  { value: 'SDVOSB', label: 'SDVOSB' },
  { value: 'Full & Open', label: 'Full & Open' },
];

const CONTRACT_TYPE_OPTIONS = [
  { value: '', label: 'Any' },
  { value: 'FFP', label: 'Firm Fixed Price (FFP)' },
  { value: 'T&M', label: 'Time & Materials (T&M)' },
  { value: 'Cost-Plus', label: 'Cost-Plus' },
];

const SOURCE_SELECTION_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'LPTA', label: 'LPTA' },
  { value: 'BV', label: 'Best Value' },
];

const CONTRACT_PRICING_TYPE_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'FFP', label: 'FFP' },
  { value: 'T&M', label: 'T&M' },
  { value: 'COST', label: 'Cost-Plus' },
];

// ---------------------------------------------------------------------------
// Comparable Awards Columns
// ---------------------------------------------------------------------------

function buildComparableColumns(): GridColDef<ComparableAward>[] {
  return [
    { field: 'contractId', headerName: 'Contract ID', flex: 1, minWidth: 150 },
    { field: 'vendor', headerName: 'Vendor', flex: 1.2, minWidth: 160 },
    {
      field: 'awardValue',
      headerName: 'Award Value',
      width: 140,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number) => formatCurrency(value, true),
    },
    {
      field: 'offers',
      headerName: 'Offers',
      width: 80,
      align: 'center',
      headerAlign: 'center',
    },
    { field: 'agency', headerName: 'Agency', flex: 1, minWidth: 140 },
    {
      field: 'awardDate',
      headerName: 'Award Date',
      width: 120,
      valueFormatter: (value: string) => formatDate(value),
    },
    {
      field: 'popMonths',
      headerName: 'POP (mo)',
      width: 90,
      align: 'center',
      headerAlign: 'center',
    },
  ];
}

// ---------------------------------------------------------------------------
// Price Range Visual
// ---------------------------------------------------------------------------

function PriceRangeBar({ low, target, high }: { low: number; high: number; target: number }) {
  const range = high - low;
  const targetPct = range > 0 ? ((target - low) / range) * 100 : 50;

  return (
    <Box sx={{ position: 'relative', height: 60, my: 2 }}>
      {/* Range bar */}
      <Box
        sx={{
          position: 'absolute',
          top: 16,
          left: 0,
          right: 0,
          height: 28,
          borderRadius: 2,
          background: 'linear-gradient(90deg, #4caf50 0%, #ff9800 50%, #f44336 100%)',
          opacity: 0.3,
        }}
      />
      {/* Target marker */}
      <Box
        sx={{
          position: 'absolute',
          top: 8,
          left: `${targetPct}%`,
          transform: 'translateX(-50%)',
          width: 4,
          height: 44,
          bgcolor: 'primary.main',
          borderRadius: 1,
        }}
      />
      {/* Labels */}
      <Typography
        variant="caption"
        sx={{ position: 'absolute', bottom: -4, left: 0, color: 'success.main', fontWeight: 600 }}
      >
        {formatCurrency(low, true)}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          bottom: -4,
          left: `${targetPct}%`,
          transform: 'translateX(-50%)',
          color: 'primary.main',
          fontWeight: 700,
        }}
      >
        {formatCurrency(target, true)}
      </Typography>
      <Typography
        variant="caption"
        sx={{ position: 'absolute', bottom: -4, right: 0, color: 'error.main', fontWeight: 600 }}
      >
        {formatCurrency(high, true)}
      </Typography>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card variant="outlined" sx={{ flex: 1, minWidth: 150 }}>
      <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PriceToWinPage() {
  const [naicsCode, setNaicsCode] = useState('');
  const [agencyName, setAgencyName] = useState('');
  const [setAsideType, setSetAsideType] = useState('');
  const [contractType, setContractType] = useState('');
  const [estimatedScope, setEstimatedScope] = useState('');
  const [sourceSelection, setSourceSelection] = useState('');
  const [contractPricingType, setContractPricingType] = useState('');

  const mutation = useMutation({
    mutationFn: (request: PriceToWinRequest) => estimatePriceToWin(request),
  });

  const result: PriceToWinResponse | undefined = mutation.data;

  const handleSubmit = useCallback(() => {
    if (!naicsCode.trim()) return;
    const request: PriceToWinRequest = {
      naicsCode: naicsCode.trim(),
      agencyName: agencyName.trim() || undefined,
      setAsideType: setAsideType || undefined,
      contractType: contractType || undefined,
      estimatedScope: estimatedScope.trim() || undefined,
      sourceSelectionCode: sourceSelection || undefined,
      contractPricingType: contractPricingType || undefined,
    };
    mutation.mutate(request);
  }, [naicsCode, agencyName, setAsideType, contractType, estimatedScope, sourceSelection, contractPricingType, mutation]);

  const comparableColumns = useMemo(() => buildComparableColumns(), []);

  return (
    <Box>
      <PageHeader
        title="Price-to-Win Estimator"
        subtitle="Estimate competitive pricing based on comparable awards"
      />

      {/* Input form */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <TextField
            size="small"
            label="NAICS Code"
            value={naicsCode}
            onChange={(e) => setNaicsCode(e.target.value)}
            required
            sx={{ minWidth: 140 }}
          />
          <TextField
            size="small"
            label="Agency"
            value={agencyName}
            onChange={(e) => setAgencyName(e.target.value)}
            sx={{ minWidth: 200 }}
          />
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel id="set-aside-label">Set-Aside Type</InputLabel>
            <Select
              labelId="set-aside-label"
              value={setAsideType}
              label="Set-Aside Type"
              onChange={(e: SelectChangeEvent) => setSetAsideType(e.target.value)}
            >
              {SET_ASIDE_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="contract-type-label">Contract Type</InputLabel>
            <Select
              labelId="contract-type-label"
              value={contractType}
              label="Contract Type"
              onChange={(e: SelectChangeEvent) => setContractType(e.target.value)}
            >
              {CONTRACT_TYPE_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel id="source-selection-label">Source Selection</InputLabel>
            <Select
              labelId="source-selection-label"
              value={sourceSelection}
              label="Source Selection"
              onChange={(e: SelectChangeEvent) => setSourceSelection(e.target.value)}
            >
              {SOURCE_SELECTION_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel id="pricing-type-label">Pricing Type</InputLabel>
            <Select
              labelId="pricing-type-label"
              value={contractPricingType}
              label="Pricing Type"
              onChange={(e: SelectChangeEvent) => setContractPricingType(e.target.value)}
            >
              {CONTRACT_PRICING_TYPE_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="Estimated Scope ($)"
            value={estimatedScope}
            onChange={(e) => setEstimatedScope(e.target.value)}
            type="number"
            sx={{ minWidth: 160 }}
          />
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!naicsCode.trim() || mutation.isPending}
          >
            Estimate
          </Button>
        </Box>
      </Paper>

      {/* Loading */}
      {mutation.isPending && <LoadingState message="Analyzing comparable awards..." />}

      {/* Error */}
      {mutation.isError && (
        <ErrorState
          title="Estimation failed"
          message="Could not generate price-to-win estimate. Please check inputs and try again."
          onRetry={handleSubmit}
        />
      )}

      {/* Results */}
      {result && (
        <Box>
          {/* Confidence bar */}
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                Confidence
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {(result.confidence * 100).toFixed(0)}% ({result.comparableCount} comparable awards)
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={result.confidence * 100}
              sx={{ height: 8, borderRadius: 1 }}
            />
          </Box>

          {/* Filter fallback warning */}
          {result.filterFallback && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Not enough comparable contracts with this filter — showing all contracts
            </Alert>
          )}

          {/* Source selection regime */}
          {result.sourceSelectionRegime && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Source Selection Regime: <strong>{result.sourceSelectionRegime}</strong>
            </Typography>
          )}

          {/* Price range */}
          <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Estimated Price Range
            </Typography>
            <PriceRangeBar
              low={result.lowEstimate}
              target={result.targetEstimate}
              high={result.highEstimate}
            />
          </Paper>

          {/* Competition stats */}
          <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
            <StatCard
              label="Avg Offers"
              value={result.competitionStats.avgOffers.toFixed(1)}
            />
            <StatCard
              label="Median Offers"
              value={result.competitionStats.medianOffers.toFixed(1)}
            />
            <StatCard
              label="Sole Source %"
              value={`${result.competitionStats.soloSourcePct.toFixed(0)}%`}
            />
            <StatCard
              label="Median Award Value"
              value={formatCurrency(result.competitionStats.medianAwardValue, true)}
            />
          </Box>

          {/* Comparable awards table */}
          {result.comparableAwards.length > 0 && (
            <Box>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Comparable Awards
              </Typography>
              <DataTable
                columns={comparableColumns}
                rows={result.comparableAwards}
                loading={false}
                getRowId={(row: ComparableAward) => row.contractId}
                sx={{ minHeight: 300 }}
              />
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
