import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GridColDef } from '@mui/x-data-grid';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton';
import Link from '@mui/material/Link';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import PlayArrowOutlinedIcon from '@mui/icons-material/PlayArrowOutlined';
import { useSnackbar } from 'notistack';

import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import {
  useSavedSearches,
  useCreateSavedSearch,
  useUpdateSavedSearch,
  useDeleteSavedSearch,
  useRunSavedSearch,
} from '@/queries/useSavedSearches';
import { formatRelative } from '@/utils/dateFormatters';
import { SAVED_SEARCH_SET_ASIDE_OPTIONS } from '@/constants/options';
import type {
  SavedSearchDto,
  SavedSearchFilterCriteria,
  CreateSavedSearchRequest,
  UpdateSavedSearchRequest,
  SavedSearchRunResultDto,
  OpportunitySearchResult,
} from '@/types/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TYPE_OPTIONS = [
  { value: 'o', label: 'Solicitation' },
  { value: 'p', label: 'Presolicitation' },
  { value: 'k', label: 'Combined Synopsis/Solicitation' },
  { value: 'r', label: 'Sources Sought' },
  { value: 'i', label: 'Intent to Bundle' },
];

const US_STATES = [
  { value: 'AL', label: 'Alabama' },
  { value: 'AK', label: 'Alaska' },
  { value: 'AZ', label: 'Arizona' },
  { value: 'AR', label: 'Arkansas' },
  { value: 'CA', label: 'California' },
  { value: 'CO', label: 'Colorado' },
  { value: 'CT', label: 'Connecticut' },
  { value: 'DE', label: 'Delaware' },
  { value: 'DC', label: 'District of Columbia' },
  { value: 'FL', label: 'Florida' },
  { value: 'GA', label: 'Georgia' },
  { value: 'HI', label: 'Hawaii' },
  { value: 'ID', label: 'Idaho' },
  { value: 'IL', label: 'Illinois' },
  { value: 'IN', label: 'Indiana' },
  { value: 'IA', label: 'Iowa' },
  { value: 'KS', label: 'Kansas' },
  { value: 'KY', label: 'Kentucky' },
  { value: 'LA', label: 'Louisiana' },
  { value: 'ME', label: 'Maine' },
  { value: 'MD', label: 'Maryland' },
  { value: 'MA', label: 'Massachusetts' },
  { value: 'MI', label: 'Michigan' },
  { value: 'MN', label: 'Minnesota' },
  { value: 'MS', label: 'Mississippi' },
  { value: 'MO', label: 'Missouri' },
  { value: 'MT', label: 'Montana' },
  { value: 'NE', label: 'Nebraska' },
  { value: 'NV', label: 'Nevada' },
  { value: 'NH', label: 'New Hampshire' },
  { value: 'NJ', label: 'New Jersey' },
  { value: 'NM', label: 'New Mexico' },
  { value: 'NY', label: 'New York' },
  { value: 'NC', label: 'North Carolina' },
  { value: 'ND', label: 'North Dakota' },
  { value: 'OH', label: 'Ohio' },
  { value: 'OK', label: 'Oklahoma' },
  { value: 'OR', label: 'Oregon' },
  { value: 'PA', label: 'Pennsylvania' },
  { value: 'PR', label: 'Puerto Rico' },
  { value: 'RI', label: 'Rhode Island' },
  { value: 'SC', label: 'South Carolina' },
  { value: 'SD', label: 'South Dakota' },
  { value: 'TN', label: 'Tennessee' },
  { value: 'TX', label: 'Texas' },
  { value: 'UT', label: 'Utah' },
  { value: 'VT', label: 'Vermont' },
  { value: 'VA', label: 'Virginia' },
  { value: 'VI', label: 'Virgin Islands' },
  { value: 'WA', label: 'Washington' },
  { value: 'WV', label: 'West Virginia' },
  { value: 'WI', label: 'Wisconsin' },
  { value: 'WY', label: 'Wyoming' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function truncate(text: string | null | undefined, maxLen: number): string {
  if (!text) return '--';
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '...';
}

function parseFilterCriteria(raw: string): SavedSearchFilterCriteria {
  try {
    return JSON.parse(raw) as SavedSearchFilterCriteria;
  } catch {
    return {};
  }
}

const EMPTY_CRITERIA: SavedSearchFilterCriteria = {
  setAsideCodes: [],
  naicsCodes: [],
  states: [],
  types: [],
  minAwardAmount: null,
  maxAwardAmount: null,
  openOnly: false,
  daysBack: null,
};

// ---------------------------------------------------------------------------
// Create / Edit Dialog
// ---------------------------------------------------------------------------

interface SearchFormState {
  searchName: string;
  description: string;
  notificationEnabled: boolean;
  criteria: SavedSearchFilterCriteria;
}

function defaultFormState(): SearchFormState {
  return {
    searchName: '',
    description: '',
    notificationEnabled: false,
    criteria: { ...EMPTY_CRITERIA },
  };
}

function formStateFromDto(dto: SavedSearchDto): SearchFormState {
  const criteria = parseFilterCriteria(dto.filterCriteria);
  return {
    searchName: dto.searchName,
    description: dto.description ?? '',
    notificationEnabled: dto.notificationEnabled === 'Y',
    criteria: { ...EMPTY_CRITERIA, ...criteria },
  };
}

interface SavedSearchDialogProps {
  open: boolean;
  editing: SavedSearchDto | null;
  onClose: () => void;
  onSave: (form: SearchFormState) => void;
  saving: boolean;
}

function SavedSearchDialog({ open, editing, onClose, onSave, saving }: SavedSearchDialogProps) {
  const [form, setForm] = useState<SearchFormState>(defaultFormState);

  // Reset form when dialog opens
  const handleEnter = useCallback(() => {
    setForm(editing ? formStateFromDto(editing) : defaultFormState());
  }, [editing]);

  const setCriteria = useCallback(
    (patch: Partial<SavedSearchFilterCriteria>) =>
      setForm((prev) => ({ ...prev, criteria: { ...prev.criteria, ...patch } })),
    [],
  );

  const valid = form.searchName.trim().length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      slotProps={{
        transition: { onEnter: handleEnter }
      }}
    >
      <DialogTitle>{editing ? 'Edit Saved Search' : 'New Saved Search'}</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label="Search Name"
            required
            fullWidth
            value={form.searchName}
            onChange={(e) => setForm((p) => ({ ...p, searchName: e.target.value }))}
          />
          <TextField
            label="Description"
            fullWidth
            multiline
            minRows={2}
            value={form.description}
            onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
          />

          <Typography
            variant="subtitle2"
            sx={{
              color: "text.secondary",
              mt: 1
            }}>
            Filter Criteria
          </Typography>

          <Autocomplete
            multiple
            options={SAVED_SEARCH_SET_ASIDE_OPTIONS}
            getOptionLabel={(o) => o.label}
            isOptionEqualToValue={(a, b) => a.value === b.value}
            value={SAVED_SEARCH_SET_ASIDE_OPTIONS.filter((o) =>
              (form.criteria.setAsideCodes ?? []).includes(o.value),
            )}
            onChange={(_e, val) => setCriteria({ setAsideCodes: val.map((v) => v.value) })}
            renderInput={(params) => <TextField {...params} label="Set-Aside Codes" />}
          />

          <TextField
            label="NAICS Codes"
            fullWidth
            placeholder="Comma-separated, e.g. 541511,541512"
            value={(form.criteria.naicsCodes ?? []).join(', ')}
            onChange={(e) => {
              const codes = e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);
              setCriteria({ naicsCodes: codes });
            }}
          />

          <Autocomplete
            multiple
            options={US_STATES}
            getOptionLabel={(o) => o.label}
            isOptionEqualToValue={(a, b) => a.value === b.value}
            value={US_STATES.filter((o) => (form.criteria.states ?? []).includes(o.value))}
            onChange={(_e, val) => setCriteria({ states: val.map((v) => v.value) })}
            renderInput={(params) => <TextField {...params} label="States" />}
          />

          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              label="Min Award Amount"
              type="number"
              fullWidth
              value={form.criteria.minAwardAmount ?? ''}
              onChange={(e) =>
                setCriteria({
                  minAwardAmount: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
            <TextField
              label="Max Award Amount"
              type="number"
              fullWidth
              value={form.criteria.maxAwardAmount ?? ''}
              onChange={(e) =>
                setCriteria({
                  maxAwardAmount: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
          </Box>

          <Autocomplete
            multiple
            options={TYPE_OPTIONS}
            getOptionLabel={(o) => o.label}
            isOptionEqualToValue={(a, b) => a.value === b.value}
            value={TYPE_OPTIONS.filter((o) => (form.criteria.types ?? []).includes(o.value))}
            onChange={(_e, val) => setCriteria({ types: val.map((v) => v.value) })}
            renderInput={(params) => <TextField {...params} label="Types" />}
          />

          <TextField
            label="Days Back"
            type="number"
            fullWidth
            value={form.criteria.daysBack ?? ''}
            onChange={(e) =>
              setCriteria({ daysBack: e.target.value ? Number(e.target.value) : null })
            }
          />

          <FormControlLabel
            control={
              <Switch
                checked={form.criteria.openOnly ?? false}
                onChange={(e) => setCriteria({ openOnly: e.target.checked })}
              />
            }
            label="Open Only"
          />

          <FormControlLabel
            control={
              <Switch
                checked={form.notificationEnabled}
                onChange={(e) => setForm((p) => ({ ...p, notificationEnabled: e.target.checked }))}
              />
            }
            label="Notifications Enabled"
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={() => onSave(form)}
          disabled={!valid || saving}
          startIcon={saving ? <CircularProgress size={16} /> : undefined}
        >
          {editing ? 'Update' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Run Results Dialog
// ---------------------------------------------------------------------------

interface RunResultsDialogProps {
  result: SavedSearchRunResultDto | null;
  onClose: () => void;
  navigate: ReturnType<typeof useNavigate>;
}

function RunResultsDialog({ result, onClose, navigate }: RunResultsDialogProps) {
  const columns = useMemo<GridColDef<OpportunitySearchResult>[]>(
    () => [
      {
        field: 'title',
        headerName: 'Title',
        flex: 2,
        minWidth: 250,
        renderCell: (params) => (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/opportunities/${encodeURIComponent(params.row.noticeId)}`);
            }}
          >
            {truncate(params.value as string | null, 80)}
          </Link>
        ),
      },
      {
        field: 'departmentName',
        headerName: 'Agency',
        flex: 1,
        minWidth: 140,
        valueFormatter: (value: string | null | undefined) => value ?? '--',
      },
      {
        field: 'setAsideDescription',
        headerName: 'Set-Aside',
        width: 140,
        valueFormatter: (value: string | null | undefined) => value ?? '--',
      },
      {
        field: 'responseDeadline',
        headerName: 'Due',
        width: 120,
        valueFormatter: (value: string | null | undefined) => {
          if (!value) return '--';
          return new Date(value).toLocaleDateString();
        },
      },
    ],
    [navigate],
  );

  if (!result) return null;

  return (
    <Dialog open onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        Results: {result.searchName}
        <Typography variant="body2" sx={{
          color: "text.secondary"
        }}>
          {result.totalCount} total, {result.newCount} new
        </Typography>
      </DialogTitle>
      <DialogContent dividers>
        {result.newCount > 0 && (
          <Chip
            label={`${result.newCount} new result${result.newCount !== 1 ? 's' : ''}`}
            color="success"
            size="small"
            sx={{ mb: 2 }}
          />
        )}
        <DataTable
          columns={columns}
          rows={result.results}
          getRowId={(row: OpportunitySearchResult) => row.noticeId}
          sx={{ minHeight: 300 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function SavedSearchesPage() {
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();

  // Data
  const { data: searches, isLoading, isError, refetch } = useSavedSearches();
  const createMutation = useCreateSavedSearch();
  const updateMutation = useUpdateSavedSearch();
  const deleteMutation = useDeleteSavedSearch();
  const runMutation = useRunSavedSearch();

  // State
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingSearch, setEditingSearch] = useState<SavedSearchDto | null>(null);
  const [runResult, setRunResult] = useState<SavedSearchRunResultDto | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SavedSearchDto | null>(null);

  // Handlers
  const handleSave = useCallback(
    (form: SearchFormState) => {
      if (editingSearch) {
        const data: UpdateSavedSearchRequest = {
          name: form.searchName,
          description: form.description || null,
          filterCriteria: form.criteria,
          notificationsEnabled: form.notificationEnabled,
        };
        updateMutation.mutate(
          { id: editingSearch.searchId, data },
          {
            onSuccess: () => {
              enqueueSnackbar('Search updated', { variant: 'success' });
              setEditingSearch(null);
            },
            onError: () => enqueueSnackbar('Failed to update search', { variant: 'error' }),
          },
        );
      } else {
        const data: CreateSavedSearchRequest = {
          searchName: form.searchName,
          description: form.description || null,
          filterCriteria: form.criteria,
          notificationEnabled: form.notificationEnabled,
        };
        createMutation.mutate(data, {
          onSuccess: () => {
            enqueueSnackbar('Search created', { variant: 'success' });
            setCreateDialogOpen(false);
          },
          onError: () => enqueueSnackbar('Failed to create search', { variant: 'error' }),
        });
      }
    },
    [editingSearch, createMutation, updateMutation, enqueueSnackbar],
  );

  const handleRun = useCallback(
    (search: SavedSearchDto) => {
      runMutation.mutate(search.searchId, {
        onSuccess: (result) => setRunResult(result),
        onError: () => enqueueSnackbar('Failed to run search', { variant: 'error' }),
      });
    },
    [runMutation, enqueueSnackbar],
  );

  const handleDelete = useCallback(() => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.searchId, {
      onSuccess: () => {
        enqueueSnackbar('Search deleted', { variant: 'success' });
        setDeleteTarget(null);
      },
      onError: () => enqueueSnackbar('Failed to delete search', { variant: 'error' }),
    });
  }, [deleteTarget, deleteMutation, enqueueSnackbar]);

  const handleToggleNotification = useCallback(
    (search: SavedSearchDto) => {
      const enabled = search.notificationEnabled !== 'Y';
      updateMutation.mutate(
        { id: search.searchId, data: { notificationsEnabled: enabled } },
        {
          onSuccess: () =>
            enqueueSnackbar(
              `Notifications ${enabled ? 'enabled' : 'disabled'}`,
              { variant: 'success' },
            ),
          onError: () => enqueueSnackbar('Failed to update notifications', { variant: 'error' }),
        },
      );
    },
    [updateMutation, enqueueSnackbar],
  );

  // Columns
  const columns = useMemo<GridColDef<SavedSearchDto>[]>(
    () => [
      {
        field: 'searchName',
        headerName: 'Name',
        flex: 1.5,
        minWidth: 180,
      },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
        valueFormatter: (value: string | null | undefined) => truncate(value, 60),
      },
      {
        field: 'lastRunAt',
        headerName: 'Last Run',
        width: 140,
        valueFormatter: (value: string | null | undefined) => formatRelative(value),
      },
      {
        field: 'lastNewResults',
        headerName: 'New Results',
        width: 110,
        align: 'center',
        headerAlign: 'center',
        renderCell: (params) => {
          const count = params.value as number | null;
          if (count == null) return '--';
          if (count > 0) {
            return <Chip label={count} size="small" color="success" />;
          }
          return <Typography variant="body2">0</Typography>;
        },
      },
      {
        field: 'notificationEnabled',
        headerName: 'Notifications',
        width: 120,
        align: 'center',
        headerAlign: 'center',
        sortable: false,
        renderCell: (params) => {
          const row = params.row as SavedSearchDto;
          return (
            <Switch
              size="small"
              checked={row.notificationEnabled === 'Y'}
              onClick={(e) => e.stopPropagation()}
              onChange={() => handleToggleNotification(row)}
            />
          );
        },
      },
      {
        field: 'actions',
        headerName: 'Actions',
        width: 140,
        sortable: false,
        renderCell: (params) => {
          const row = params.row as SavedSearchDto;
          return (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Tooltip title="Run search">
                <IconButton
                  size="small"
                  color="primary"
                  aria-label="Run search"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRun(row);
                  }}
                  disabled={runMutation.isPending}
                >
                  <PlayArrowOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Edit">
                <IconButton
                  size="small"
                  aria-label="Edit search"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingSearch(row);
                  }}
                >
                  <EditOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete">
                <IconButton
                  size="small"
                  color="error"
                  aria-label="Delete search"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteTarget(row);
                  }}
                >
                  <DeleteOutlineIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          );
        },
      },
    ],
    [handleRun, handleToggleNotification, runMutation.isPending],
  );

  // Render
  if (isError) {
    return (
      <Box>
        <PageHeader title="Saved Searches" subtitle="Manage your saved opportunity searches" />
        <ErrorState
          title="Failed to load saved searches"
          message="Could not retrieve your saved searches. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Saved Searches"
        subtitle="Manage your saved opportunity searches"
        actions={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateDialogOpen(true)}
          >
            New Saved Search
          </Button>
        }
      />

      {isLoading && <LoadingState message="Loading saved searches..." />}

      {!isLoading && (
        <DataTable
          columns={columns}
          rows={searches ?? []}
          loading={false}
          getRowId={(row: SavedSearchDto) => row.searchId}
          sx={{ minHeight: 400 }}
        />
      )}

      {/* Create / Edit Dialog */}
      <SavedSearchDialog
        open={createDialogOpen || editingSearch != null}
        editing={editingSearch}
        onClose={() => {
          setCreateDialogOpen(false);
          setEditingSearch(null);
        }}
        onSave={handleSave}
        saving={createMutation.isPending || updateMutation.isPending}
      />

      {/* Run Results Dialog */}
      <RunResultsDialog
        result={runResult}
        onClose={() => setRunResult(null)}
        navigate={navigate}
      />

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={deleteTarget != null}
        title="Delete Saved Search"
        message={`Are you sure you want to delete "${deleteTarget?.searchName ?? ''}"? This action cannot be undone.`}
        severity="error"
        confirmText="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        loading={deleteMutation.isPending}
      />
    </Box>
  );
}
