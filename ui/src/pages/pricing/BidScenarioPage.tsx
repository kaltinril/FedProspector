import { useCallback, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import IconButton from '@mui/material/IconButton';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import Tab from '@mui/material/Tab';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Autocomplete from '@mui/material/Autocomplete';
import AddOutlined from '@mui/icons-material/AddOutlined';
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';
import DownloadOutlined from '@mui/icons-material/DownloadOutlined';
import GppGoodOutlined from '@mui/icons-material/GppGoodOutlined';
import { BarChart } from '@mui/x-charts/BarChart';

import { PageHeader } from '@/components/shared/PageHeader';
import { searchLaborCategories, checkScaCompliance } from '@/api/pricing';
import { queryKeys } from '@/queries/queryKeys';
import { formatCurrency } from '@/utils/formatters';
import { useDebounce } from '@/hooks/useDebounce';
import type {
  BidScenario,
  LaborLine,
  CanonicalCategory,
  ScaComplianceResponse,
  ScaComplianceResult,
} from '@/types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let nextId = 1;
function genId(): string {
  return `id-${nextId++}`;
}

function emptyLaborLine(): LaborLine {
  return { id: genId(), category: '', hours: 0, rate: 0 };
}

function emptyScenario(name: string): BidScenario {
  return {
    id: genId(),
    name,
    laborLines: [emptyLaborLine()],
    overheadRate: 0,
    gaRate: 0,
    feeRate: 0,
    odcs: 0,
    subcontractorCost: 0,
    travel: 0,
  };
}

function computeTotals(scenario: BidScenario) {
  const directLabor = scenario.laborLines.reduce((sum, l) => sum + l.hours * l.rate, 0);
  const overhead = directLabor * (scenario.overheadRate / 100);
  const subtotalBeforeGa = directLabor + overhead;
  const ga = subtotalBeforeGa * (scenario.gaRate / 100);
  const totalCost = subtotalBeforeGa + ga + scenario.odcs + scenario.subcontractorCost + scenario.travel;
  const fee = totalCost * (scenario.feeRate / 100);
  const totalPrice = totalCost + fee;
  return { directLabor, overhead, ga, totalCost, fee, totalPrice };
}

function escapeCSV(val: string | number): string {
  const str = String(val);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function exportCsv(scenarios: BidScenario[]) {
  const headers = ['Scenario', 'Category', 'Hours', 'Rate', 'Line Total', 'Overhead %', 'G&A %', 'Fee %', 'ODCs', 'Subcontractor', 'Travel', 'Total Price'];
  const rows: string[][] = [];
  for (const s of scenarios) {
    const totals = computeTotals(s);
    for (const line of s.laborLines) {
      rows.push([
        escapeCSV(s.name),
        escapeCSV(line.category),
        escapeCSV(line.hours),
        escapeCSV(line.rate),
        escapeCSV(line.hours * line.rate),
        escapeCSV(s.overheadRate),
        escapeCSV(s.gaRate),
        escapeCSV(s.feeRate),
        escapeCSV(s.odcs),
        escapeCSV(s.subcontractorCost),
        escapeCSV(s.travel),
        escapeCSV(totals.totalPrice),
      ]);
    }
  }
  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'bid-scenarios.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Category Autocomplete
// ---------------------------------------------------------------------------

function CategoryAutocomplete({
  value,
  onChange,
}: {
  value: string;
  onChange: (val: string, canonicalId?: number) => void;
}) {
  const [inputValue, setInputValue] = useState(value);
  const debouncedQuery = useDebounce(inputValue, 300);

  const { data: options = [] } = useQuery({
    queryKey: queryKeys.pricing.categorySearch(debouncedQuery),
    queryFn: () => searchLaborCategories(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Autocomplete
      freeSolo
      size="small"
      options={options}
      getOptionLabel={(opt: string | CanonicalCategory) =>
        typeof opt === 'string' ? opt : opt.name
      }
      inputValue={inputValue}
      onInputChange={(_, newValue) => {
        setInputValue(newValue);
        onChange(newValue);
      }}
      onChange={(_, selected) => {
        if (selected && typeof selected !== 'string') {
          onChange(selected.name, selected.id);
        }
      }}
      renderInput={(params) => <TextField {...params} label="Category" sx={{ minWidth: 200 }} />}
      sx={{ minWidth: 200 }}
    />
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BidScenarioPage() {
  const [scenarios, setScenarios] = useState<BidScenario[]>([emptyScenario('Scenario 1')]);
  const [activeTab, setActiveTab] = useState(0);

  const addScenario = useCallback(() => {
    if (scenarios.length >= 3) return;
    setScenarios((prev) => [...prev, emptyScenario(`Scenario ${prev.length + 1}`)]);
    setActiveTab(scenarios.length);
  }, [scenarios.length]);

  const updateScenario = useCallback((index: number, updates: Partial<BidScenario>) => {
    setScenarios((prev) => prev.map((s, i) => (i === index ? { ...s, ...updates } : s)));
  }, []);

  const updateLaborLine = useCallback(
    (scenarioIdx: number, lineIdx: number, updates: Partial<LaborLine>) => {
      setScenarios((prev) =>
        prev.map((s, si) =>
          si === scenarioIdx
            ? {
                ...s,
                laborLines: s.laborLines.map((l, li) =>
                  li === lineIdx ? { ...l, ...updates } : l,
                ),
              }
            : s,
        ),
      );
    },
    [],
  );

  const addLaborLine = useCallback((scenarioIdx: number) => {
    setScenarios((prev) =>
      prev.map((s, i) =>
        i === scenarioIdx ? { ...s, laborLines: [...s.laborLines, emptyLaborLine()] } : s,
      ),
    );
  }, []);

  const removeLaborLine = useCallback((scenarioIdx: number, lineIdx: number) => {
    setScenarios((prev) =>
      prev.map((s, i) =>
        i === scenarioIdx
          ? { ...s, laborLines: s.laborLines.filter((_, li) => li !== lineIdx) }
          : s,
      ),
    );
  }, []);

  const current = scenarios[activeTab];
  const currentTotals = current ? computeTotals(current) : null;

  // Chart data for comparison
  const chartData = useMemo(() => {
    return scenarios.map((s) => ({
      name: s.name,
      totalPrice: computeTotals(s).totalPrice,
    }));
  }, [scenarios]);

  return (
    <Box>
      <PageHeader
        title="Bid Scenario Modeler"
        subtitle="Build and compare pricing scenarios side-by-side"
        actions={
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<DownloadOutlined />}
              onClick={() => exportCsv(scenarios)}
            >
              Export CSV
            </Button>
            <Button
              variant="contained"
              startIcon={<AddOutlined />}
              onClick={addScenario}
              disabled={scenarios.length >= 3}
            >
              Add Scenario
            </Button>
          </Box>
        }
      />

      {/* Scenario tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)}>
          {scenarios.map((s, i) => (
            <Tab key={s.id} label={s.name} id={`scenario-tab-${i}`} />
          ))}
        </Tabs>
      </Box>

      {current && currentTotals && (
        <Box>
          {/* Scenario name */}
          <TextField
            size="small"
            label="Scenario Name"
            value={current.name}
            onChange={(e) => updateScenario(activeTab, { name: e.target.value })}
            sx={{ mb: 2, minWidth: 250 }}
          />

          {/* Labor lines */}
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Labor Lines
            </Typography>
            {current.laborLines.map((line, li) => (
              <Box key={line.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                <CategoryAutocomplete
                  value={line.category}
                  onChange={(val, canonicalId) =>
                    updateLaborLine(activeTab, li, { category: val, ...(canonicalId != null ? { canonicalId } : {}) })
                  }
                />
                <TextField
                  size="small"
                  label="Hours"
                  type="number"
                  value={line.hours || ''}
                  onChange={(e) =>
                    updateLaborLine(activeTab, li, { hours: Number(e.target.value) || 0 })
                  }
                  sx={{ width: 100 }}
                />
                <TextField
                  size="small"
                  label="Rate ($/hr)"
                  type="number"
                  value={line.rate || ''}
                  onChange={(e) =>
                    updateLaborLine(activeTab, li, { rate: Number(e.target.value) || 0 })
                  }
                  sx={{ width: 120 }}
                />
                <Typography variant="body2" sx={{ minWidth: 100, textAlign: 'right' }}>
                  {formatCurrency(line.hours * line.rate)}
                </Typography>
                <IconButton
                  size="small"
                  onClick={() => removeLaborLine(activeTab, li)}
                  disabled={current.laborLines.length <= 1}
                >
                  <DeleteOutlined fontSize="small" />
                </IconButton>
              </Box>
            ))}
            <Button
              size="small"
              startIcon={<AddOutlined />}
              onClick={() => addLaborLine(activeTab)}
            >
              Add Labor Line
            </Button>
          </Paper>

          {/* Cost structure */}
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Cost Structure
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <TextField
                size="small"
                label="Overhead %"
                type="number"
                value={current.overheadRate || ''}
                onChange={(e) =>
                  updateScenario(activeTab, { overheadRate: Number(e.target.value) || 0 })
                }
                sx={{ width: 120 }}
              />
              <TextField
                size="small"
                label="G&A %"
                type="number"
                value={current.gaRate || ''}
                onChange={(e) =>
                  updateScenario(activeTab, { gaRate: Number(e.target.value) || 0 })
                }
                sx={{ width: 120 }}
              />
              <TextField
                size="small"
                label="Fee %"
                type="number"
                value={current.feeRate || ''}
                onChange={(e) =>
                  updateScenario(activeTab, { feeRate: Number(e.target.value) || 0 })
                }
                sx={{ width: 120 }}
              />
              <TextField
                size="small"
                label="ODCs ($)"
                type="number"
                value={current.odcs || ''}
                onChange={(e) =>
                  updateScenario(activeTab, { odcs: Number(e.target.value) || 0 })
                }
                sx={{ width: 140 }}
              />
              <TextField
                size="small"
                label="Subcontractor ($)"
                type="number"
                value={current.subcontractorCost || ''}
                onChange={(e) =>
                  updateScenario(activeTab, {
                    subcontractorCost: Number(e.target.value) || 0,
                  })
                }
                sx={{ width: 160 }}
              />
              <TextField
                size="small"
                label="Travel ($)"
                type="number"
                value={current.travel || ''}
                onChange={(e) =>
                  updateScenario(activeTab, { travel: Number(e.target.value) || 0 })
                }
                sx={{ width: 140 }}
              />
            </Box>
          </Paper>

          {/* Computed totals */}
          <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
            <Card variant="outlined" sx={{ flex: 1, minWidth: 130 }}>
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography variant="caption" color="text.secondary">Direct Labor</Typography>
                <Typography variant="h6" fontWeight={600}>
                  {formatCurrency(currentTotals.directLabor)}
                </Typography>
              </CardContent>
            </Card>
            <Card variant="outlined" sx={{ flex: 1, minWidth: 130 }}>
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography variant="caption" color="text.secondary">Indirect Costs</Typography>
                <Typography variant="h6" fontWeight={600}>
                  {formatCurrency(currentTotals.overhead + currentTotals.ga)}
                </Typography>
              </CardContent>
            </Card>
            <Card variant="outlined" sx={{ flex: 1, minWidth: 130 }}>
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography variant="caption" color="text.secondary">Total Cost</Typography>
                <Typography variant="h6" fontWeight={600}>
                  {formatCurrency(currentTotals.totalCost)}
                </Typography>
              </CardContent>
            </Card>
            <Card variant="outlined" sx={{ flex: 1, minWidth: 130 }}>
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography variant="caption" color="text.secondary">Fee</Typography>
                <Typography variant="h6" fontWeight={600}>
                  {formatCurrency(currentTotals.fee)}
                </Typography>
              </CardContent>
            </Card>
            <Card variant="outlined" sx={{ flex: 1, minWidth: 130 }}>
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography variant="caption" color="text.secondary">Total Price</Typography>
                <Typography variant="h5" fontWeight={700} color="primary.main">
                  {formatCurrency(currentTotals.totalPrice)}
                </Typography>
              </CardContent>
            </Card>
          </Box>
        </Box>
      )}

      {/* SCA Compliance Check */}
      {current && <ScaComplianceSection scenario={current} />}

      {/* Comparison chart */}
      {scenarios.length > 1 && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Scenario Comparison
          </Typography>
          <BarChart
            xAxis={[{ scaleType: 'band', data: chartData.map((d) => d.name) }]}
            series={[{ data: chartData.map((d) => d.totalPrice), label: 'Total Price' }]}
            height={300}
          />
        </Paper>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// SCA Compliance Section
// ---------------------------------------------------------------------------

const SCA_US_STATES = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
  'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
  'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
  'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
  'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
];

function statusColor(status: string): string {
  switch (status) {
    case 'Compliant': return '#4caf50';
    case 'Violation': return '#f44336';
    default: return '#9e9e9e';
  }
}

function ScaComplianceSection({ scenario }: { scenario: BidScenario }) {
  const [scaState, setScaState] = useState('');
  const [county, setCounty] = useState('');
  const [result, setResult] = useState<ScaComplianceResponse | null>(null);

  const mutation = useMutation({
    mutationFn: checkScaCompliance,
    onSuccess: (data) => setResult(data),
  });

  const hasLinesWithIds = scenario.laborLines.some((l) => l.canonicalId != null);

  const handleCheck = () => {
    const lineItems = scenario.laborLines
      .filter((l) => l.canonicalId != null && l.rate > 0)
      .map((l) => ({
        canonicalId: l.canonicalId!,
        proposedRate: l.rate,
        includesFringe: false,
      }));

    if (lineItems.length === 0) return;

    mutation.mutate({
      state: scaState || null,
      county: county || null,
      lineItems,
    });
  };

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Typography variant="subtitle1" fontWeight={600} gutterBottom>
        SCA Compliance Check
      </Typography>

      {/* Work location */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel id="sca-comp-state-label">State</InputLabel>
          <Select
            labelId="sca-comp-state-label"
            value={scaState}
            label="State"
            onChange={(e: SelectChangeEvent) => {
              setScaState(e.target.value);
              setResult(null);
            }}
          >
            <MenuItem value="">Select State</MenuItem>
            {SCA_US_STATES.map((s) => (
              <MenuItem key={s} value={s}>{s}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField
          size="small"
          label="County (optional)"
          value={county}
          onChange={(e) => {
            setCounty(e.target.value);
            setResult(null);
          }}
          sx={{ minWidth: 160 }}
        />

        <Button
          variant="contained"
          startIcon={<GppGoodOutlined />}
          onClick={handleCheck}
          disabled={!hasLinesWithIds || mutation.isPending}
        >
          {mutation.isPending ? 'Checking...' : 'Check SCA Compliance'}
        </Button>
      </Box>

      {!hasLinesWithIds && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Select labor categories from the autocomplete to enable compliance checking.
        </Typography>
      )}

      {mutation.isError && (
        <Typography variant="body2" color="error" sx={{ mb: 1 }}>
          Failed to check compliance. Please try again.
        </Typography>
      )}

      {/* Results */}
      {result && (
        <Box>
          {/* Summary chips */}
          <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
            <Chip
              label={`${result.compliantCount} Compliant`}
              color="success"
              size="small"
              variant="outlined"
            />
            <Chip
              label={`${result.violationCount} Violation${result.violationCount !== 1 ? 's' : ''}`}
              color="error"
              size="small"
              variant={result.violationCount > 0 ? 'filled' : 'outlined'}
            />
            <Chip
              label={`${result.unmappedCount} Unmapped`}
              size="small"
              variant="outlined"
            />
            <Chip
              label={`Fringe Obligation: ${formatCurrency(result.totalFringeObligation)}`}
              size="small"
              variant="outlined"
              color="info"
            />
          </Box>

          {/* Results table */}
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Category</TableCell>
                  <TableCell align="right">Proposed Rate</TableCell>
                  <TableCell align="right">SCA Minimum</TableCell>
                  <TableCell align="right">SCA Fringe</TableCell>
                  <TableCell align="right">SCA Full Cost</TableCell>
                  <TableCell align="center">Status</TableCell>
                  <TableCell align="right">Shortfall</TableCell>
                  <TableCell>WD #</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {result.results.map((r: ScaComplianceResult) => (
                  <TableRow key={r.canonicalId}>
                    <TableCell>{r.canonicalName}</TableCell>
                    <TableCell align="right">{formatCurrency(r.proposedRate)}</TableCell>
                    <TableCell align="right">
                      {r.scaMinimumRate != null ? formatCurrency(r.scaMinimumRate) : '--'}
                    </TableCell>
                    <TableCell align="right">
                      {r.scaFringe != null ? formatCurrency(r.scaFringe) : '--'}
                    </TableCell>
                    <TableCell align="right">
                      {r.scaFullCost != null ? formatCurrency(r.scaFullCost) : '--'}
                    </TableCell>
                    <TableCell align="center">
                      <Typography
                        variant="body2"
                        sx={{ color: statusColor(r.status), fontWeight: 600 }}
                      >
                        {r.status}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      {r.shortfall != null ? (
                        <Typography variant="body2" color="error">
                          {formatCurrency(r.shortfall)}
                        </Typography>
                      ) : '--'}
                    </TableCell>
                    <TableCell>{r.wdNumber ?? '--'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
    </Paper>
  );
}
