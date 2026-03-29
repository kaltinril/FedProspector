import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { GridColDef, GridPaginationModel, GridSortModel, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import InputAdornment from '@mui/material/InputAdornment';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import SearchIcon from '@mui/icons-material/Search';
import ViewListIcon from '@mui/icons-material/ViewList';

import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { StatusChip } from '@/components/shared/StatusChip';
import { HierarchyTree } from '@/components/hierarchy/HierarchyTree';
import { HierarchyRefreshPanel } from '@/components/hierarchy/HierarchyRefreshPanel';
import { useHierarchySearch } from '@/queries/useHierarchy';
import { useDebounce } from '@/hooks/useDebounce';
import { useAuth } from '@/auth/useAuth';
import type { FederalOrgListItem } from '@/types/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

type StatusFilter = 'Active' | 'Inactive' | 'All';
type ViewMode = 'tree' | 'list';
type LevelFilter = '1' | '2' | '3' | 'All';

// ---------------------------------------------------------------------------
// URL <-> filter helpers
// ---------------------------------------------------------------------------

function readFiltersFromParams(params: URLSearchParams) {
  const rawView = params.get('view');
  return {
    keyword: params.get('keyword') ?? '',
    status: (params.get('status') ?? 'Active') as StatusFilter,
    level: (params.get('level') ?? 'All') as LevelFilter,
    view: (rawView === 'list' ? 'list' : 'tree') as ViewMode,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function HierarchyBrowsePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isSystemAdmin } = useAuth();

  // Filters from URL
  const filters = useMemo(() => readFiltersFromParams(searchParams), [searchParams]);

  // Local keyword with 800ms debounce — long enough to not fire mid-word
  const [localKeyword, setLocalKeyword] = useState(filters.keyword);
  const debouncedKeyword = useDebounce(localKeyword, 500);

  // Sync local keyword with URL on external changes (back/forward)
  useEffect(() => {
    setLocalKeyword(filters.keyword);
  }, [filters.keyword]);

  // Commit debounced keyword to URL
  useEffect(() => {
    if (debouncedKeyword !== filters.keyword) {
      const params = new URLSearchParams(searchParams);
      if (debouncedKeyword) {
        params.set('keyword', debouncedKeyword);
      } else {
        params.delete('keyword');
      }
      setSearchParams(params, { replace: true });
    }
  }, [debouncedKeyword, filters.keyword, searchParams, setSearchParams]);

  // --- Handlers ---
  const updateUrlParam = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams);
      if (value && !(key === 'level' && value === 'All') && !(key === 'view' && value === 'tree')) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const statusParam = filters.status === 'All' ? undefined : filters.status;
  const levelParam = filters.level === 'All' ? undefined : Number(filters.level);

  // List view: pagination and sorting
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ page: 0, pageSize: 25 });
  const [sortModel, setSortModel] = useState<GridSortModel>([]);

  // Reset pagination when filters change
  useEffect(() => {
    setPaginationModel((prev) => ({ ...prev, page: 0 }));
  }, [debouncedKeyword, statusParam, levelParam]);

  // Search query — runs in list mode
  const queryParams = useMemo(
    () => ({
      keyword: debouncedKeyword || undefined,
      status: statusParam,
      level: levelParam,
      page: paginationModel.page + 1,
      pageSize: paginationModel.pageSize,
      sortBy: sortModel[0]?.field,
      sortDescending: sortModel[0]?.sort === 'desc',
    }),
    [debouncedKeyword, statusParam, levelParam, paginationModel, sortModel],
  );
  const { data: searchResults, isLoading: isSearching } = useHierarchySearch(queryParams);

  const handleTreeSelect = useCallback(
    (fhOrgId: string, _name: string) => {
      navigate(`/hierarchy/${encodeURIComponent(fhOrgId)}`);
    },
    [navigate],
  );

  const handleRowClick = useCallback(
    (params: GridRowParams<FederalOrgListItem>) => {
      navigate(`/hierarchy/${encodeURIComponent(params.row.fhOrgId)}`);
    },
    [navigate],
  );

  const isTreeView = filters.view === 'tree';

  const listColumns = useMemo<GridColDef<FederalOrgListItem>[]>(
    () => [
      { field: 'fhOrgName', headerName: 'Name', flex: 1, minWidth: 300 },
      {
        field: 'fhOrgType',
        headerName: 'Type',
        width: 160,
        renderCell: ({ value }) => <Chip label={value} size="small" />,
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        renderCell: ({ value }) => <StatusChip status={value} />,
      },
      { field: 'agencyCode', headerName: 'Agency Code', width: 130 },
      { field: 'cgac', headerName: 'CGAC', width: 100 },
      { field: 'level', headerName: 'Level', width: 80, type: 'number' },
    ],
    [],
  );

  return (
    <Box>
      <PageHeader
        title="Federal Hierarchy"
        subtitle="Browse and search the federal government organization structure"
      />

      {/* Admin refresh panel */}
      {isSystemAdmin && <HierarchyRefreshPanel />}

      {/* Toolbar: Search | Status | Level | View */}
      <Box
        sx={{
          display: 'flex',
          gap: 2,
          mb: 2,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <TextField
          size="small"
          placeholder="Search organizations..."
          value={localKeyword}
          onChange={(e) => setLocalKeyword(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ minWidth: 260 }}
        />
        <ToggleButtonGroup
          size="small"
          exclusive
          value={filters.status}
          onChange={(_, value) => {
            if (value) updateUrlParam('status', value);
          }}
        >
          <ToggleButton value="Active">Active</ToggleButton>
          <ToggleButton value="Inactive">Inactive</ToggleButton>
          <ToggleButton value="All">All</ToggleButton>
        </ToggleButtonGroup>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={filters.view}
          onChange={(_, value) => {
            if (value) updateUrlParam('view', value);
          }}
        >
          <ToggleButton value="tree" aria-label="Tree view">
            <AccountTreeIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton value="list" aria-label="List view">
            <ViewListIcon fontSize="small" />
          </ToggleButton>
        </ToggleButtonGroup>
        {!isTreeView && (
          <ToggleButtonGroup
            size="small"
            exclusive
            value={filters.level}
            onChange={(_, value) => {
              if (value) updateUrlParam('level', value);
            }}
          >
            <ToggleButton value="1">Level 1</ToggleButton>
            <ToggleButton value="2">Level 2</ToggleButton>
            <ToggleButton value="3">Level 3</ToggleButton>
            <ToggleButton value="All">All</ToggleButton>
          </ToggleButtonGroup>
        )}
      </Box>

      <Paper
        variant="outlined"
        sx={{
          maxHeight: 'calc(100vh - 280px)',
          overflowY: 'auto',
        }}
      >
        {isTreeView ? (
          <>
            <Typography
              variant="subtitle2"
              sx={{ px: 2, pt: 1.5, pb: 1, borderBottom: 1, borderColor: 'divider' }}
            >
              Organization Tree
            </Typography>
            <HierarchyTree keyword={debouncedKeyword || undefined} status={statusParam} onSelect={handleTreeSelect} />
          </>
        ) : (
          <DataTable<FederalOrgListItem>
            columns={listColumns}
            rows={searchResults?.items ?? []}
            loading={isSearching}
            rowCount={searchResults?.totalCount ?? 0}
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            sortModel={sortModel}
            onSortModelChange={setSortModel}
            onRowClick={handleRowClick}
            getRowId={(row) => row.fhOrgId}
            sx={{ minHeight: 400 }}
          />
        )}
      </Paper>
    </Box>
  );
}
