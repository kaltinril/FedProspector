import { useState } from 'react';
import {
  Box,
  Grid,
  TextField,
  Button,
  Typography,
  Autocomplete,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Alert,
  CircularProgress,
  Collapse,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useDebounce } from '@/hooks/useDebounce';
import { useNaicsSearch } from '@/queries/useOrganization';
import type { NaicsSearchDto } from '@/types/organization';

export interface PastPerformanceEntry {
  contractNumber: string;
  agencyName: string;
  description: string;
  naicsCode: string;
  contractValue: number | null;
  periodStart: string | null;
  periodEnd: string | null;
}

interface PastPerformanceStepProps {
  pastPerformances: PastPerformanceEntry[];
  skipPastPerformance: boolean;
  hasUei: boolean;
  onChange: (pastPerformances: PastPerformanceEntry[], skip: boolean) => void;
  onNext: () => void;
  onBack: () => void;
}

const emptyEntry: PastPerformanceEntry = {
  contractNumber: '',
  agencyName: '',
  description: '',
  naicsCode: '',
  contractValue: null,
  periodStart: null,
  periodEnd: null,
};

export function PastPerformanceStep({
  pastPerformances,
  skipPastPerformance,
  hasUei,
  onChange,
  onNext,
  onBack,
}: PastPerformanceStepProps) {
  const [formOpen, setFormOpen] = useState(false);
  const [current, setCurrent] = useState<PastPerformanceEntry>({ ...emptyEntry });
  const [naicsInput, setNaicsInput] = useState('');
  const debouncedNaics = useDebounce(naicsInput, 300);
  const { data: naicsResults, isLoading: searchingNaics } = useNaicsSearch(debouncedNaics);

  const handleAdd = () => {
    if (!current.contractNumber && !current.agencyName) return;
    onChange([...pastPerformances, { ...current }], false);
    setCurrent({ ...emptyEntry });
    setNaicsInput('');
    setFormOpen(false);
  };

  const handleRemove = (index: number) => {
    const updated = pastPerformances.filter((_, i) => i !== index);
    onChange(updated, skipPastPerformance);
  };

  const handleSkip = () => {
    onChange([], true);
    onNext();
  };

  const formatCurrency = (value: number | null) => {
    if (value == null) return '';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
  };

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 1 }}>
        Past Performance
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Add relevant contract history. This step is optional.
      </Typography>

      <Button variant="outlined" onClick={handleSkip} sx={{ mb: 3 }}>
        Skip for Now
      </Button>

      {hasUei && (
        <Alert severity="info" sx={{ mb: 2 }}>
          After setup, you can view contracts associated with your UEI from the Organization
          settings.
        </Alert>
      )}

      {/* Add Contract Form */}
      <Paper variant="outlined" sx={{ mb: 3 }}>
        <Button
          fullWidth
          onClick={() => setFormOpen(!formOpen)}
          startIcon={formOpen ? <ExpandLessIcon /> : <AddIcon />}
          endIcon={formOpen ? undefined : <ExpandMoreIcon />}
          sx={{ justifyContent: 'flex-start', px: 2, py: 1.5 }}
        >
          {formOpen ? 'Collapse' : 'Add Contract'}
        </Button>
        <Collapse in={formOpen}>
          <Box sx={{ p: 2, pt: 0 }}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Contract Number"
                  fullWidth
                  value={current.contractNumber}
                  onChange={(e) =>
                    setCurrent({ ...current, contractNumber: e.target.value })
                  }
                  slotProps={{ htmlInput: { maxLength: 50 } }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Agency Name"
                  fullWidth
                  value={current.agencyName}
                  onChange={(e) =>
                    setCurrent({ ...current, agencyName: e.target.value })
                  }
                  slotProps={{ htmlInput: { maxLength: 200 } }}
                />
              </Grid>
              <Grid size={12}>
                <TextField
                  label="Description"
                  fullWidth
                  multiline
                  minRows={2}
                  value={current.description}
                  onChange={(e) =>
                    setCurrent({ ...current, description: e.target.value })
                  }
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <Autocomplete
                  options={naicsResults ?? []}
                  getOptionLabel={(opt) => `${opt.code} - ${opt.title}`}
                  filterOptions={(x) => x}
                  loading={searchingNaics}
                  inputValue={naicsInput}
                  onInputChange={(_e, value) => setNaicsInput(value)}
                  onChange={(_e, value: NaicsSearchDto | null) =>
                    setCurrent({ ...current, naicsCode: value?.code ?? '' })
                  }
                  value={null}
                  blurOnSelect
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="NAICS Code"
                      slotProps={{
                        input: {
                          ...params.InputProps,
                          endAdornment: (
                            <>
                              {searchingNaics ? <CircularProgress size={20} /> : null}
                              {params.InputProps.endAdornment}
                            </>
                          ),
                        },
                      }}
                    />
                  )}
                  noOptionsText={
                    debouncedNaics.length < 2 ? 'Type at least 2 characters' : 'No results'
                  }
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Contract Value ($)"
                  type="number"
                  fullWidth
                  value={current.contractValue ?? ''}
                  onChange={(e) =>
                    setCurrent({
                      ...current,
                      contractValue: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Performance Period Start"
                  type="date"
                  fullWidth
                  value={current.periodStart ?? ''}
                  onChange={(e) =>
                    setCurrent({ ...current, periodStart: e.target.value || null })
                  }
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Performance Period End"
                  type="date"
                  fullWidth
                  value={current.periodEnd ?? ''}
                  onChange={(e) =>
                    setCurrent({ ...current, periodEnd: e.target.value || null })
                  }
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Grid>
              <Grid size={12}>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={handleAdd}
                  disabled={!current.contractNumber && !current.agencyName}
                >
                  Add Contract
                </Button>
              </Grid>
            </Grid>
          </Box>
        </Collapse>
      </Paper>

      {/* Contracts List */}
      {pastPerformances.length > 0 && (
        <TableContainer component={Paper} variant="outlined" sx={{ mb: 3 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Contract #</TableCell>
                <TableCell>Agency</TableCell>
                <TableCell>NAICS</TableCell>
                <TableCell align="right">Value</TableCell>
                <TableCell align="center" width={60} />
              </TableRow>
            </TableHead>
            <TableBody>
              {pastPerformances.map((pp, index) => (
                <TableRow key={index}>
                  <TableCell>{pp.contractNumber || '-'}</TableCell>
                  <TableCell>{pp.agencyName || '-'}</TableCell>
                  <TableCell>{pp.naicsCode || '-'}</TableCell>
                  <TableCell align="right">{formatCurrency(pp.contractValue)}</TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      onClick={() => handleRemove(index)}
                      color="error"
                      aria-label="Remove past performance entry"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" size="large" onClick={onNext}>
          Next
        </Button>
      </Box>
    </Box>
  );
}
