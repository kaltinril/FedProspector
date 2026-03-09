import { useState } from 'react';
import {
  Box,
  Grid,
  TextField,
  Button,
  Typography,
  Autocomplete,
  IconButton,
  Radio,
  Checkbox,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  MenuItem,
  Alert,
  CircularProgress,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useDebounce } from '@/hooks/useDebounce';
import { useNaicsSearch } from '@/queries/useOrganization';
import type { NaicsSearchDto } from '@/types/organization';

export interface NaicsCodeEntry {
  naicsCode: string;
  naicsTitle: string;
  isPrimary: boolean;
  sizeStandardMet: boolean;
}

export interface NaicsStepData {
  naicsCodes: NaicsCodeEntry[];
  employeeCount: number | null;
  annualRevenue: number | null;
  fiscalYearEndMonth: number;
}

interface NaicsCodesStepProps {
  data: NaicsStepData;
  onChange: (data: NaicsStepData) => void;
  onNext: () => void;
  onBack: () => void;
}

const MONTHS = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
];

export function NaicsCodesStep({ data, onChange, onNext, onBack }: NaicsCodesStepProps) {
  const [searchInput, setSearchInput] = useState('');
  const [validationError, setValidationError] = useState('');
  const debouncedSearch = useDebounce(searchInput, 300);
  const { data: searchResults, isLoading: searching } = useNaicsSearch(debouncedSearch);

  const handleAddNaics = (_event: unknown, value: NaicsSearchDto | null) => {
    if (!value) return;
    if (data.naicsCodes.some((n) => n.naicsCode === value.code)) return;

    const newEntry: NaicsCodeEntry = {
      naicsCode: value.code,
      naicsTitle: value.title,
      isPrimary: data.naicsCodes.length === 0,
      sizeStandardMet: false,
    };
    onChange({ ...data, naicsCodes: [...data.naicsCodes, newEntry] });
    setSearchInput('');
    setValidationError('');
  };

  const handleRemove = (code: string) => {
    const updated = data.naicsCodes.filter((n) => n.naicsCode !== code);
    if (updated.length > 0 && !updated.some((n) => n.isPrimary)) {
      updated[0].isPrimary = true;
    }
    onChange({ ...data, naicsCodes: updated });
  };

  const handleSetPrimary = (code: string) => {
    const updated = data.naicsCodes.map((n) => ({
      ...n,
      isPrimary: n.naicsCode === code,
    }));
    onChange({ ...data, naicsCodes: updated });
  };

  const handleToggleSizeStandard = (code: string) => {
    const updated = data.naicsCodes.map((n) =>
      n.naicsCode === code ? { ...n, sizeStandardMet: !n.sizeStandardMet } : n,
    );
    onChange({ ...data, naicsCodes: updated });
  };

  const handleNext = () => {
    if (data.naicsCodes.length === 0) {
      setValidationError('At least one NAICS code is required.');
      return;
    }
    if (!data.naicsCodes.some((n) => n.isPrimary)) {
      setValidationError('Exactly one NAICS code must be marked as primary.');
      return;
    }
    setValidationError('');
    onNext();
  };

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        NAICS Codes & Size Standards
      </Typography>

      <Autocomplete
        options={searchResults ?? []}
        getOptionLabel={(option) => `${option.code} - ${option.title}`}
        filterOptions={(x) => x}
        loading={searching}
        inputValue={searchInput}
        onInputChange={(_e, value) => setSearchInput(value)}
        onChange={handleAddNaics}
        value={null}
        blurOnSelect
        clearOnBlur
        renderInput={(params) => (
          <TextField
            {...params}
            label="Search NAICS Codes"
            placeholder="Type code or keyword..."
            slotProps={{
              input: {
                ...params.InputProps,
                endAdornment: (
                  <>
                    {searching ? <CircularProgress size={20} /> : null}
                    {params.InputProps.endAdornment}
                  </>
                ),
              },
            }}
          />
        )}
        noOptionsText={debouncedSearch.length < 2 ? 'Type at least 2 characters' : 'No results'}
        sx={{ mb: 3 }}
      />

      {validationError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {validationError}
        </Alert>
      )}

      {data.naicsCodes.length > 0 && (
        <TableContainer component={Paper} variant="outlined" sx={{ mb: 3 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>NAICS Code</TableCell>
                <TableCell>Title</TableCell>
                <TableCell align="center">Primary</TableCell>
                <TableCell align="center">Meets Size Standard</TableCell>
                <TableCell align="center" width={60} />
              </TableRow>
            </TableHead>
            <TableBody>
              {data.naicsCodes.map((entry) => (
                <TableRow key={entry.naicsCode}>
                  <TableCell>{entry.naicsCode}</TableCell>
                  <TableCell>{entry.naicsTitle}</TableCell>
                  <TableCell align="center">
                    <Radio
                      checked={entry.isPrimary}
                      onChange={() => handleSetPrimary(entry.naicsCode)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Checkbox
                      checked={entry.sizeStandardMet}
                      onChange={() => handleToggleSizeStandard(entry.naicsCode)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      onClick={() => handleRemove(entry.naicsCode)}
                      color="error"
                      aria-label={`Remove NAICS code ${entry.naicsCode}`}
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

      <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2, mb: 1 }}>
        Size Standard Information
      </Typography>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <TextField
            label="Employee Count"
            type="number"
            fullWidth
            value={data.employeeCount ?? ''}
            onChange={(e) =>
              onChange({
                ...data,
                employeeCount: e.target.value ? Number(e.target.value) : null,
              })
            }
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <TextField
            label="Annual Revenue ($)"
            type="number"
            fullWidth
            value={data.annualRevenue ?? ''}
            onChange={(e) =>
              onChange({
                ...data,
                annualRevenue: e.target.value ? Number(e.target.value) : null,
              })
            }
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <TextField
            select
            label="Fiscal Year End Month"
            fullWidth
            value={data.fiscalYearEndMonth}
            onChange={(e) =>
              onChange({ ...data, fiscalYearEndMonth: Number(e.target.value) })
            }
          >
            {MONTHS.map((m) => (
              <MenuItem key={m.value} value={m.value}>
                {m.label}
              </MenuItem>
            ))}
          </TextField>
        </Grid>
      </Grid>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" size="large" onClick={handleNext}>
          Next
        </Button>
      </Box>
    </Box>
  );
}
