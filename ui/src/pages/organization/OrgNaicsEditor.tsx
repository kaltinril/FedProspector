import { useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  IconButton,
  Paper,
  Radio,
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
import { useDebounce } from '@/hooks/useDebounce';
import { useNaicsSearch, useSetOrgNaics } from '@/queries/useOrganization';
import type { NaicsSearchDto, OrgNaicsDto } from '@/types/organization';

/**
 * Phase 136 Unit A: editable list of the org's OWN registered NAICS codes with the
 * primary clearly flagged. Mirrors the single-primary validation from the onboarding
 * wizard (NaicsCodesStep): exactly one primary, no duplicates, 6-digit codes. Saves the
 * full list via PUT /org/naics (SetNaicsAsync full-replace). Read-only when canEdit=false.
 */
interface OrgNaicsEditorProps {
  naics: OrgNaicsDto[];
  canEdit: boolean;
}

export function OrgNaicsEditor({ naics, canEdit }: OrgNaicsEditorProps) {
  const setNaicsMutation = useSetOrgNaics();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<OrgNaicsDto[]>([]);
  const [searchInput, setSearchInput] = useState('');
  const [error, setError] = useState('');
  const debouncedSearch = useDebounce(searchInput, 300);
  const { data: searchResults, isLoading: searching } = useNaicsSearch(debouncedSearch);

  const handleStart = () => {
    setDraft(naics.map((n) => ({ ...n })));
    setError('');
    setEditing(true);
  };

  const handleCancel = () => {
    setEditing(false);
    setError('');
    setSearchInput('');
  };

  const handleAdd = (_event: unknown, value: NaicsSearchDto | null) => {
    if (!value) return;
    if (draft.some((n) => n.naicsCode === value.code)) return;
    setDraft([
      ...draft,
      {
        naicsCode: value.code,
        isPrimary: draft.length === 0,
        sizeStandardMet: false,
      },
    ]);
    setSearchInput('');
    setError('');
  };

  const handleRemove = (code: string) => {
    const updated = draft.filter((n) => n.naicsCode !== code);
    // Keep exactly one primary: if the removed code was primary, promote the first remaining.
    if (updated.length > 0 && !updated.some((n) => n.isPrimary)) {
      updated[0] = { ...updated[0], isPrimary: true };
    }
    setDraft(updated);
  };

  const handleSetPrimary = (code: string) => {
    setDraft(draft.map((n) => ({ ...n, isPrimary: n.naicsCode === code })));
  };

  const handleSave = () => {
    if (draft.length === 0) {
      setError('At least one NAICS code is required.');
      return;
    }
    if (draft.filter((n) => n.isPrimary).length !== 1) {
      setError('Exactly one NAICS code must be marked as primary.');
      return;
    }
    setNaicsMutation.mutate(draft, {
      onSuccess: () => {
        setEditing(false);
        setSearchInput('');
        setError('');
      },
      onError: (err) => {
        setError(err instanceof Error ? err.message : 'Failed to save NAICS codes');
      },
    });
  };

  const rows = editing ? draft : naics;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          NAICS Codes
        </Typography>
        {canEdit && !editing && (
          <Button variant="outlined" size="small" onClick={handleStart}>
            Edit
          </Button>
        )}
      </Box>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
        Your organization&apos;s registered NAICS codes. Exactly one is the primary code.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {editing && (
        <Autocomplete
          options={searchResults ?? []}
          getOptionLabel={(option) => `${option.code} - ${option.title}`}
          filterOptions={(x) => x}
          loading={searching}
          inputValue={searchInput}
          onInputChange={(_e, value) => setSearchInput(value)}
          onChange={handleAdd}
          value={null}
          blurOnSelect
          clearOnBlur
          renderInput={(params) => (
            <TextField
              {...params}
              label="Add NAICS Code"
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
          noOptionsText={debouncedSearch.length < 2 ? 'Type at least 2 characters' : 'No results'}
          sx={{ mb: 2 }}
        />
      )}

      {rows.length === 0 ? (
        <Alert severity="info">No NAICS codes set.</Alert>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>NAICS Code</TableCell>
                <TableCell align="center">Primary</TableCell>
                {editing && <TableCell align="center" width={60} />}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((entry) => (
                <TableRow key={entry.naicsCode}>
                  <TableCell>{entry.naicsCode}</TableCell>
                  <TableCell align="center">
                    {editing ? (
                      <Radio
                        checked={entry.isPrimary}
                        onChange={() => handleSetPrimary(entry.naicsCode)}
                        size="small"
                      />
                    ) : entry.isPrimary ? (
                      'Primary'
                    ) : (
                      ''
                    )}
                  </TableCell>
                  {editing && (
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleRemove(entry.naicsCode)}
                        aria-label={`Remove NAICS code ${entry.naicsCode}`}
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

      {editing && (
        <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
          <Button variant="contained" onClick={handleSave} disabled={setNaicsMutation.isPending}>
            Save
          </Button>
          <Button variant="outlined" onClick={handleCancel} disabled={setNaicsMutation.isPending}>
            Cancel
          </Button>
        </Box>
      )}
    </Box>
  );
}
