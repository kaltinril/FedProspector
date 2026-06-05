import { useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSnackbar } from 'notistack';
import { useDebounce } from '@/hooks/useDebounce';
import {
  useAssociatedNaics,
  useAddAssociatedNaics,
  useDeleteAssociatedNaics,
  useNaicsSearch,
  useOrgNaics,
} from '@/queries/useOrganization';
import { LoadingState } from '@/components/shared/LoadingState';
import type { NaicsSearchDto } from '@/types/organization';

/**
 * Phase 136 Unit G: manage the org's manually-curated "associated" NAICS codes — codes the
 * org declares relevant BEYOND its registered (own) NAICS and linked-entity codes. Validates
 * 6-digit codes, dedups, and disallows codes already in the org's registered NAICS so the two
 * lists stay distinct. Wiring associated NAICS into recommendations is a later integration step.
 */
interface AssociatedNaicsEditorProps {
  canEdit: boolean;
}

export function AssociatedNaicsEditor({ canEdit }: AssociatedNaicsEditorProps) {
  const { enqueueSnackbar } = useSnackbar();
  const { data: associated = [], isLoading } = useAssociatedNaics();
  const { data: ownNaics = [] } = useOrgNaics();
  const addMutation = useAddAssociatedNaics();
  const deleteMutation = useDeleteAssociatedNaics();

  const [selected, setSelected] = useState<NaicsSearchDto | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const debouncedSearch = useDebounce(searchInput, 300);
  const { data: searchResults, isLoading: searching } = useNaicsSearch(debouncedSearch);

  // Phase 136 follow-up: prevent duplicates at the source — hide codes that are already on the
  // associated list OR already among the org's registered NAICS so they can't be picked again.
  const excludedCodes = new Set<string>([
    ...associated.map((a) => a.naicsCode),
    ...ownNaics.map((n) => n.naicsCode),
  ]);
  const availableOptions = (searchResults ?? []).filter((o) => !excludedCodes.has(o.code));
  // Distinguish "type more" from "everything matched is already added" in the empty state.
  const allMatchesExcluded =
    debouncedSearch.length >= 2 && (searchResults?.length ?? 0) > 0 && availableOptions.length === 0;

  const handleAdd = () => {
    if (!selected) {
      setError('Select a NAICS code to add.');
      return;
    }
    const code = selected.code.trim();
    if (code.length !== 6 || !/^\d{6}$/.test(code)) {
      setError('Associated NAICS code must be exactly 6 digits.');
      return;
    }
    if (associated.some((a) => a.naicsCode === code)) {
      setError('That code is already in your associated list.');
      return;
    }
    if (ownNaics.some((n) => n.naicsCode === code)) {
      setError('That code is already one of your registered NAICS codes.');
      return;
    }
    addMutation.mutate(
      { naicsCode: code, note: note.trim() || null },
      {
        onSuccess: (result) => {
          setSelected(null);
          setSearchInput('');
          setNote('');
          setError('');
          // The backend is idempotent: a code already on the list returns the existing row with
          // alreadyExisted=true. Surface that as a neutral "already added" rather than a fresh add.
          if (result.alreadyExisted) {
            enqueueSnackbar(`NAICS ${code} is already on your associated list`, { variant: 'info' });
          } else {
            enqueueSnackbar('Associated NAICS added', { variant: 'success' });
          }
        },
        onError: (err) => {
          setError(err instanceof Error ? err.message : 'Failed to add associated NAICS');
        },
      },
    );
  };

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id, {
      onSuccess: () => enqueueSnackbar('Associated NAICS removed', { variant: 'success' }),
      onError: () => enqueueSnackbar('Failed to remove associated NAICS', { variant: 'error' }),
    });
  };

  if (isLoading) return <LoadingState message="Loading associated NAICS..." />;

  return (
    <Box>
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Associated NAICS Codes
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
        A manually-curated list of NAICS codes you consider relevant beyond your registered codes
        and linked entities. Keep this distinct from your registered NAICS.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {canEdit && (
        <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <Autocomplete
            options={availableOptions}
            getOptionLabel={(option) => `${option.code} - ${option.title}`}
            filterOptions={(x) => x}
            loading={searching}
            inputValue={searchInput}
            onInputChange={(_e, value) => setSearchInput(value)}
            value={selected}
            onChange={(_e, value) => setSelected(value)}
            isOptionEqualToValue={(opt, val) => opt.code === val.code}
            sx={{ flex: 1, minWidth: 260 }}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Search NAICS Code"
                placeholder="Type code or keyword..."
                size="small"
                slotProps={{
                  ...params.slotProps,
                  input: {
                    ...params.slotProps.input,
                    endAdornment: (
                      <>
                        {searching ? <CircularProgress size={20} /> : null}
                        {params.slotProps.input.endAdornment}
                      </>
                    ),
                  },
                }}
              />
            )}
            noOptionsText={
              debouncedSearch.length < 2
                ? 'Type at least 2 characters'
                : allMatchesExcluded
                  ? 'All matches are already in your registered or associated NAICS'
                  : 'No results'
            }
          />
          <TextField
            label="Note (optional)"
            size="small"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            sx={{ flex: 1, minWidth: 200 }}
          />
          <Button
            variant="contained"
            onClick={handleAdd}
            disabled={addMutation.isPending || !selected}
            sx={{ flexShrink: 0 }}
          >
            Add
          </Button>
        </Box>
      )}

      {associated.length === 0 ? (
        <Alert severity="info">No associated NAICS codes yet.</Alert>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>NAICS Code</TableCell>
                <TableCell>Note</TableCell>
                {canEdit && <TableCell align="center" width={60} />}
              </TableRow>
            </TableHead>
            <TableBody>
              {associated.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{row.naicsCode}</TableCell>
                  <TableCell>{row.note || '-'}</TableCell>
                  {canEdit && (
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleDelete(row.id)}
                        disabled={deleteMutation.isPending}
                        aria-label={`Remove associated NAICS code ${row.naicsCode}`}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
