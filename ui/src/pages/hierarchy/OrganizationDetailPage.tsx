import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import type { GridColDef, GridPaginationModel, GridSortModel, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Breadcrumbs from '@mui/material/Breadcrumbs';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import AccountTreeOutlined from '@mui/icons-material/AccountTreeOutlined';

import { PageHeader } from '@/components/shared/PageHeader';
import { BackToSearch } from '@/components/shared/BackToSearch';
import { TabbedDetailPage } from '@/components/shared/TabbedDetailPage';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { DataTable } from '@/components/shared/DataTable';
import { StatusChip } from '@/components/shared/StatusChip';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import {
  useHierarchyDetail,
  useHierarchySearch,
  useHierarchyOpportunities,
} from '@/queries/useHierarchy';
import { useDebounce } from '@/hooks/useDebounce';
import { formatDate, formatDateTime } from '@/utils/dateFormatters';
import type {
  FederalOrgDetail,
  FederalOrgListItem,
  FederalOrgBreadcrumb,
  OpportunitySearchResult,
} from '@/types/api';

// ---------------------------------------------------------------------------
// Type chip color by org level
// ---------------------------------------------------------------------------

const TYPE_CHIP_COLOR: Record<string, 'primary' | 'secondary' | 'info' | 'default'> = {
  Department: 'primary',
  'Sub-Tier': 'secondary',
  Office: 'info',
};

// ---------------------------------------------------------------------------
// Children tab
// ---------------------------------------------------------------------------

function ChildrenTab({ fhOrgId }: { fhOrgId: string }) {
  const navigate = useNavigate();
  const [nameFilter, setNameFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ page: 0, pageSize: 25 });
  const [sortModel, setSortModel] = useState<GridSortModel>([]);

  // Reset page when filters change
  const debouncedName = useDebounce(nameFilter, 500);
  useEffect(() => {
    setPaginationModel((prev) => ({ ...prev, page: 0 }));
  }, [debouncedName, typeFilter, statusFilter]);

  const { data, isLoading, isFetching } = useHierarchySearch({
    parentOrgId: fhOrgId,
    keyword: debouncedName || undefined,
    fhOrgType: typeFilter === 'all' ? undefined : typeFilter,
    status: statusFilter === 'all' ? undefined : statusFilter,
    page: paginationModel.page + 1,
    pageSize: paginationModel.pageSize,
    sortBy: sortModel[0]?.field,
    sortDescending: sortModel[0]?.sort === 'desc',
  });

  const columns: GridColDef<FederalOrgListItem>[] = useMemo(
    () => [
      {
        field: 'fhOrgName',
        headerName: 'Name',
        flex: 2,
        minWidth: 200,
        renderCell: (params) => (
          <Typography variant="body2" sx={{ color: 'primary.main', cursor: 'pointer' }}>
            {params.value}
          </Typography>
        ),
      },
      {
        field: 'fhOrgType',
        headerName: 'Type',
        width: 140,
        renderCell: (params) => (
          <Chip
            label={params.value}
            size="small"
            color={TYPE_CHIP_COLOR[params.value as string] ?? 'default'}
            variant="outlined"
          />
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 100,
        renderCell: (params) =>
          params.value ? <StatusChip status={params.value} /> : null,
      },
      {
        field: 'cgac',
        headerName: 'CGAC',
        width: 80,
        valueGetter: (_value, row) => row.cgac ?? '--',
      },
    ],
    [],
  );

  const handleRowClick = useCallback(
    (params: GridRowParams<FederalOrgListItem>) => {
      navigate(`/hierarchy/${encodeURIComponent(params.row.fhOrgId)}`);
    },
    [navigate],
  );

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          size="small"
          placeholder="Filter by name..."
          value={nameFilter}
          onChange={(e) => setNameFilter(e.target.value)}
          sx={{ minWidth: 220 }}
        />
        <TextField
          size="small"
          select
          label="Type"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          sx={{ minWidth: 150 }}
        >
          <MenuItem value="all">All</MenuItem>
          <MenuItem value="Department/Ind. Agency">Department</MenuItem>
          <MenuItem value="Sub-Tier">Sub-Tier</MenuItem>
          <MenuItem value="OFFICE">Office</MenuItem>
          <MenuItem value="MAJOR COMMAND">Major Command</MenuItem>
        </TextField>
        <TextField
          size="small"
          select
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          sx={{ minWidth: 120 }}
        >
          <MenuItem value="all">All</MenuItem>
          <MenuItem value="Active">Active</MenuItem>
          <MenuItem value="Inactive">Inactive</MenuItem>
        </TextField>
      </Box>
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        loading={isLoading || isFetching}
        rowCount={data?.totalCount ?? 0}
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        sortModel={sortModel}
        onSortModelChange={setSortModel}
        onRowClick={handleRowClick}
        getRowId={(row: FederalOrgListItem) => row.fhOrgId}
        sx={{ minHeight: 300 }}
      />
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Opportunities tab
// ---------------------------------------------------------------------------

function OpportunitiesTab({ fhOrgId }: { fhOrgId: string }) {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState('Y');
  const [typeFilter, setTypeFilter] = useState('all');
  const [setAsideFilter, setSetAsideFilter] = useState('all');
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [sortModel, setSortModel] = useState<GridSortModel>([]);

  // Reset page when filters change
  useEffect(() => {
    setPaginationModel((prev) => ({ ...prev, page: 0 }));
  }, [activeFilter, typeFilter, setAsideFilter]);

  const { data, isLoading, isFetching } = useHierarchyOpportunities(fhOrgId, {
    page: paginationModel.page + 1,
    pageSize: paginationModel.pageSize,
    sortBy: sortModel[0]?.field,
    sortDescending: sortModel[0]?.sort === 'desc',
    active: activeFilter === 'all' ? undefined : activeFilter,
    type: typeFilter === 'all' ? undefined : typeFilter,
    setAsideCode: setAsideFilter === 'all' ? undefined : setAsideFilter,
  });

  const columns: GridColDef<OpportunitySearchResult>[] = useMemo(
    () => [
      {
        field: 'title',
        headerName: 'Title',
        flex: 2,
        minWidth: 220,
        renderCell: (params) => (
          <Typography
            variant="body2"
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              color: 'primary.main',
              cursor: 'pointer',
            }}
          >
            {params.value ?? '--'}
          </Typography>
        ),
      },
      {
        field: 'solicitationNumber',
        headerName: 'Solicitation #',
        width: 150,
        valueGetter: (_value, row) => row.solicitationNumber ?? '--',
      },
      {
        field: 'departmentName',
        headerName: 'Department',
        width: 150,
        valueGetter: (_value, row) => row.departmentName ?? '--',
      },
      {
        field: 'responseDeadline',
        headerName: 'Response Deadline',
        width: 150,
        valueGetter: (_value, row) =>
          row.responseDeadline
            ? new Date(row.responseDeadline).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })
            : '--',
      },
      {
        field: 'setAsideDescription',
        headerName: 'Set-Aside',
        width: 150,
        valueGetter: (_value, row) => row.setAsideDescription ?? '--',
      },
      {
        field: 'baseAndAllOptions',
        headerName: 'Est. Value',
        width: 130,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params) => (
          <CurrencyDisplay value={params.row.baseAndAllOptions} compact />
        ),
      },
    ],
    [],
  );

  const handleRowClick = useCallback(
    (params: GridRowParams<OpportunitySearchResult>) => {
      navigate(`/opportunities/${encodeURIComponent(params.row.noticeId)}`);
    },
    [navigate],
  );

  const hasFilters = activeFilter !== 'all' || typeFilter !== 'all' || setAsideFilter !== 'all';

  if (!isLoading && (data?.totalCount ?? 0) === 0 && !hasFilters) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
        No opportunities found for this organization.
      </Typography>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={activeFilter}
            label="Status"
            onChange={(e) => setActiveFilter(e.target.value)}
          >
            <MenuItem value="Y">Open</MenuItem>
            <MenuItem value="all">All</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Type</InputLabel>
          <Select
            value={typeFilter}
            label="Type"
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="Combined Synopsis/Solicitation">Combined Synopsis/Solicitation</MenuItem>
            <MenuItem value="Solicitation">Solicitation</MenuItem>
            <MenuItem value="Award Notice">Award Notice</MenuItem>
            <MenuItem value="Sources Sought">Sources Sought</MenuItem>
            <MenuItem value="Presolicitation">Presolicitation</MenuItem>
            <MenuItem value="Special Notice">Special Notice</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Set-Aside</InputLabel>
          <Select
            value={setAsideFilter}
            label="Set-Aside"
            onChange={(e) => setSetAsideFilter(e.target.value)}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="SBA">Total Small Business</MenuItem>
            <MenuItem value="SDVOSBC">SDVOSB</MenuItem>
            <MenuItem value="HZC">HUBZone</MenuItem>
            <MenuItem value="WOSB">WOSB</MenuItem>
            <MenuItem value="8A">8(a) Competed</MenuItem>
            <MenuItem value="8AN">8(a) Sole Source</MenuItem>
            <MenuItem value="EDWOSB">EDWOSB</MenuItem>
            <MenuItem value="NONE">No Set-Aside</MenuItem>
          </Select>
        </FormControl>
      </Box>
      {!isLoading && (data?.totalCount ?? 0) === 0 && hasFilters ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
          No opportunities match the selected filters.
        </Typography>
      ) : (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          loading={isLoading || isFetching}
          rowCount={data?.totalCount ?? 0}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          sortModel={sortModel}
          onSortModelChange={setSortModel}
          onRowClick={handleRowClick}
          getRowId={(row: OpportunitySearchResult) => row.noticeId}
          sx={{ minHeight: 300 }}
        />
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function OrganizationDetailPage() {
  const { fhOrgId } = useParams<{ fhOrgId: string }>();
  const { data: org, isLoading, isError, refetch } = useHierarchyDetail(fhOrgId ?? '');

  if (isLoading) {
    return (
      <Box>
        <BackToSearch searchPath="/hierarchy" label="Back to hierarchy" />
        <LoadingState message="Loading organization..." />
      </Box>
    );
  }

  if (isError || !org) {
    return (
      <Box>
        <BackToSearch searchPath="/hierarchy" label="Back to hierarchy" />
        <ErrorState
          title="Organization not found"
          message="Could not load organization details. The organization may not exist or there was an error."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  const hasChildren = (org.childCount ?? 0) > 0;
  const showChildrenTab = org.level != null && org.level < 3;

  const tabs = [
    {
      label: 'Overview',
      value: 'overview',
      content: <OverviewTab org={org} />,
    },
    ...(showChildrenTab
      ? [
          {
            label: `Children${hasChildren ? ` (${org.childCount})` : ''}`,
            value: 'children',
            content: hasChildren ? (
              <ChildrenTab fhOrgId={org.fhOrgId} />
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                No child organizations.
              </Typography>
            ),
          },
        ]
      : []),
    {
      label: 'Opportunities',
      value: 'opportunities',
      content: <OpportunitiesTab fhOrgId={org.fhOrgId} />,
    },
  ];

  return (
    <Box>
      <BackToSearch searchPath="/hierarchy" label="Back to hierarchy" />

      {/* Breadcrumb from parent chain */}
      {org.parentChain && org.parentChain.length > 0 && (
        <Breadcrumbs sx={{ mb: 2 }} aria-label="organization hierarchy">
          <Link
            component={RouterLink}
            to="/hierarchy"
            underline="hover"
            color="inherit"
            sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
          >
            <AccountTreeOutlined sx={{ fontSize: 18 }} />
            Hierarchy
          </Link>
          {org.parentChain.map((parent: FederalOrgBreadcrumb) => (
            <Link
              key={parent.fhOrgId}
              component={RouterLink}
              to={`/hierarchy/${encodeURIComponent(parent.fhOrgId)}`}
              underline="hover"
              color="inherit"
            >
              {parent.fhOrgName}
            </Link>
          ))}
          <Typography color="text.primary" sx={{ fontWeight: 500 }}>
            {org.fhOrgName}
          </Typography>
        </Breadcrumbs>
      )}

      {/* Header */}
      <PageHeader
        title={org.fhOrgName}
        actions={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              label={org.fhOrgType}
              color={TYPE_CHIP_COLOR[org.fhOrgType] ?? 'default'}
              variant="outlined"
            />
            <StatusChip status={org.status} />
          </Box>
        }
      />

      {/* Identifier chips below header */}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
        {org.agencyCode && (
          <Chip label={`Agency: ${org.agencyCode}`} size="small" variant="outlined" />
        )}
        {org.cgac && (
          <Chip label={`CGAC: ${org.cgac}`} size="small" variant="outlined" />
        )}
        {org.oldfpdsOfficeCode && (
          <Chip label={`FPDS: ${org.oldfpdsOfficeCode}`} size="small" variant="outlined" />
        )}
      </Box>

      <TabbedDetailPage tabs={tabs} />
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Overview tab
// ---------------------------------------------------------------------------

function OverviewTab({ org }: { org: FederalOrgDetail }) {
  const facts = [
    { label: 'Organization Type', value: org.fhOrgType },
    { label: 'Status', value: org.status },
    { label: 'Level', value: `Level ${org.level}` },
    { label: 'Agency Code', value: org.agencyCode },
    { label: 'CGAC', value: org.cgac },
    { label: 'FPDS Office Code', value: org.oldfpdsOfficeCode },
    {
      label: 'Parent Organization',
      value: org.parentOrgId ? (
        <Link
          component={RouterLink}
          to={`/hierarchy/${encodeURIComponent(org.parentOrgId)}`}
          underline="hover"
        >
          {org.parentChain && org.parentChain.length > 0
            ? org.parentChain[org.parentChain.length - 1].fhOrgName
            : org.parentOrgId}
        </Link>
      ) : (
        'None (top-level)'
      ),
    },
    { label: 'Description', value: org.description, fullWidth: true },
    { label: 'Created Date', value: formatDate(org.createdDate) },
    { label: 'Last Modified', value: formatDateTime(org.lastModifiedDate) },
    { label: 'Last Loaded', value: formatDateTime(org.lastLoadedAt) },
  ];

  return (
    <Paper variant="outlined" sx={{ p: 3 }}>
      <KeyFactsGrid facts={facts} columns={2} />
    </Paper>
  );
}
