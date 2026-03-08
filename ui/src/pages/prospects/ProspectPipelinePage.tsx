import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';
import { useQueryClient } from '@tanstack/react-query';
import type { GridColDef, GridPaginationModel, GridSortModel, GridRowParams } from '@mui/x-data-grid';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import type { DragStartEvent, DragEndEvent, DragOverEvent } from '@dnd-kit/core';
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useDroppable } from '@dnd-kit/core';
import { differenceInDays, parseISO, isValid } from 'date-fns';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import FormControl from '@mui/material/FormControl';
import IconButton from '@mui/material/IconButton';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import FlagIcon from '@mui/icons-material/Flag';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import ViewListIcon from '@mui/icons-material/ViewList';

import { PageHeader } from '@/components/shared/PageHeader';
import { StatusChip } from '@/components/shared/StatusChip';
import { EmptyState } from '@/components/shared/EmptyState';
import { DataTable } from '@/components/shared/DataTable';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { DeadlineCountdown } from '@/components/shared/DeadlineCountdown';

import { useProspectSearch, useUpdateProspectStatus } from '@/queries/useProspects';
import { queryKeys } from '@/queries/queryKeys';
import { useAuth } from '@/auth';
import { formatCurrency } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import type { ProspectListDto, ProspectSearchParams } from '@/types/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const KANBAN_STATUSES = ['NEW', 'REVIEWING', 'PURSUING', 'BID_SUBMITTED', 'WON', 'LOST'] as const;

const STATUS_LABELS: Record<string, string> = {
  NEW: 'New',
  REVIEWING: 'Reviewing',
  PURSUING: 'Pursuing',
  BID_SUBMITTED: 'Bid Submitted',
  WON: 'Won',
  LOST: 'Lost',
  DECLINED: 'Declined',
};

/** Valid transitions for the prospect status state machine. */
const VALID_TRANSITIONS: Record<string, string[]> = {
  NEW: ['REVIEWING', 'DECLINED'],
  REVIEWING: ['PURSUING', 'DECLINED'],
  PURSUING: ['BID_SUBMITTED', 'DECLINED'],
  BID_SUBMITTED: ['WON', 'LOST'],
};

function isValidTransition(from: string, to: string): boolean {
  return VALID_TRANSITIONS[from]?.includes(to) ?? false;
}

function isDeadlineUrgent(deadline: string | null | undefined): boolean {
  if (!deadline) return false;
  const parsed = parseISO(deadline);
  if (!isValid(parsed)) return false;
  return differenceInDays(parsed, new Date()) < 7;
}

type ViewMode = 'kanban' | 'list';

// ---------------------------------------------------------------------------
// FilterBar
// ---------------------------------------------------------------------------

interface FilterBarProps {
  filters: {
    myProspects: boolean;
    dueThisWeek: boolean;
    highPriority: boolean;
    status: string;
  };
  onToggleMyProspects: () => void;
  onToggleDueThisWeek: () => void;
  onToggleHighPriority: () => void;
  onStatusChange: (status: string) => void;
}

function FilterBar({
  filters,
  onToggleMyProspects,
  onToggleDueThisWeek,
  onToggleHighPriority,
  onStatusChange,
}: FilterBarProps) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, flexWrap: 'wrap' }}>
      <Chip
        label="My Prospects"
        variant={filters.myProspects ? 'filled' : 'outlined'}
        color={filters.myProspects ? 'primary' : 'default'}
        onClick={onToggleMyProspects}
        clickable
      />
      <Chip
        label="Due This Week"
        variant={filters.dueThisWeek ? 'filled' : 'outlined'}
        color={filters.dueThisWeek ? 'warning' : 'default'}
        onClick={onToggleDueThisWeek}
        clickable
      />
      <Chip
        label="High Priority"
        variant={filters.highPriority ? 'filled' : 'outlined'}
        color={filters.highPriority ? 'error' : 'default'}
        onClick={onToggleHighPriority}
        clickable
      />
      <FormControl size="small" sx={{ minWidth: 140, ml: 'auto' }}>
        <InputLabel id="status-filter-label">Status</InputLabel>
        <Select
          labelId="status-filter-label"
          value={filters.status}
          label="Status"
          onChange={(e: SelectChangeEvent) => onStatusChange(e.target.value)}
        >
          <MenuItem value="">All</MenuItem>
          {KANBAN_STATUSES.map((s) => (
            <MenuItem key={s} value={s}>
              {STATUS_LABELS[s]}
            </MenuItem>
          ))}
          <MenuItem value="DECLINED">Declined</MenuItem>
        </Select>
      </FormControl>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// ProspectCard (for Kanban)
// ---------------------------------------------------------------------------

interface ProspectCardProps {
  prospect: ProspectListDto;
  onClick: (id: number) => void;
  isDragOverlay?: boolean;
}

function ProspectCardContent({ prospect, onClick, isDragOverlay }: ProspectCardProps) {
  const urgent = isDeadlineUrgent(prospect.responseDeadline);

  return (
    <Card
      variant="outlined"
      onClick={() => onClick(prospect.prospectId)}
      sx={{
        mb: 1,
        cursor: 'pointer',
        bgcolor: urgent ? 'error.50' : 'background.paper',
        borderColor: urgent ? 'error.light' : undefined,
        opacity: isDragOverlay ? 0.9 : 1,
        '&:hover': { borderColor: 'primary.main' },
      }}
    >
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
          <DragIndicatorIcon
            fontSize="small"
            sx={{ color: 'text.disabled', mt: 0.25, flexShrink: 0 }}
          />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="body2"
              fontWeight={600}
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {prospect.opportunityTitle ?? 'Untitled'}
            </Typography>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
              <DeadlineCountdown deadline={prospect.responseDeadline ?? null} showDate={false} />
              {prospect.estimatedValue != null && (
                <Typography variant="caption" color="text.secondary">
                  {formatCurrency(prospect.estimatedValue, true)}
                </Typography>
              )}
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
              {prospect.assignedToName && (
                <Typography variant="caption" color="text.secondary">
                  {prospect.assignedToName}
                </Typography>
              )}
              {prospect.priority === 'HIGH' && (
                <FlagIcon fontSize="small" color="error" sx={{ fontSize: 14 }} />
              )}
              {prospect.goNoGoScore != null && (
                <Chip
                  label={`Score: ${prospect.goNoGoScore}`}
                  size="small"
                  variant="outlined"
                  sx={{ height: 20, fontSize: '0.7rem' }}
                />
              )}
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

function SortableProspectCard({ prospect, onClick }: ProspectCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: prospect.prospectId });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <ProspectCardContent prospect={prospect} onClick={onClick} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// KanbanColumn
// ---------------------------------------------------------------------------

interface KanbanColumnProps {
  status: string;
  prospects: ProspectListDto[];
  isLoading: boolean;
  onCardClick: (id: number) => void;
}

function KanbanColumn({ status, prospects, isLoading, onCardClick }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const ids = useMemo(() => prospects.map((p) => p.prospectId), [prospects]);

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      sx={{
        flex: '1 1 0',
        minWidth: 220,
        maxWidth: 320,
        display: 'flex',
        flexDirection: 'column',
        bgcolor: isOver ? 'action.hover' : 'background.default',
        transition: 'background-color 0.2s',
      }}
    >
      <Box
        sx={{
          p: 1.5,
          borderBottom: 1,
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Typography variant="subtitle2">{STATUS_LABELS[status] ?? status}</Typography>
        <Chip label={prospects.length} size="small" variant="outlined" />
      </Box>
      <Box sx={{ p: 1, flex: 1, overflowY: 'auto', minHeight: 100 }}>
        {isLoading ? (
          <Stack spacing={1}>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} variant="rectangular" height={80} sx={{ borderRadius: 1 }} />
            ))}
          </Stack>
        ) : (
          <SortableContext items={ids} strategy={verticalListSortingStrategy}>
            {prospects.map((p) => (
              <SortableProspectCard key={p.prospectId} prospect={p} onClick={onCardClick} />
            ))}
          </SortableContext>
        )}
      </Box>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// KanbanView
// ---------------------------------------------------------------------------

interface KanbanViewProps {
  prospects: ProspectListDto[];
  isLoading: boolean;
  onCardClick: (id: number) => void;
  onStatusChange: (id: number, fromStatus: string, toStatus: string) => void;
}

function KanbanView({ prospects, isLoading, onCardClick, onStatusChange }: KanbanViewProps) {
  const [activeCard, setActiveCard] = useState<ProspectListDto | null>(null);
  const [archivedOpen, setArchivedOpen] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const columnData = useMemo(() => {
    const map: Record<string, ProspectListDto[]> = {};
    for (const s of KANBAN_STATUSES) map[s] = [];
    map['DECLINED'] = [];
    for (const p of prospects) {
      const bucket = map[p.status];
      if (bucket) bucket.push(p);
      else if (map['NEW']) map['NEW'].push(p); // fallback
    }
    return map;
  }, [prospects]);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const card = prospects.find((p) => p.prospectId === event.active.id);
      setActiveCard(card ?? null);
    },
    [prospects],
  );

  const handleDragOver = useCallback((_event: DragOverEvent) => {
    // No-op: visual feedback handled by isOver in KanbanColumn
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveCard(null);
      const { active, over } = event;
      if (!over) return;

      const card = prospects.find((p) => p.prospectId === active.id);
      if (!card) return;

      // Determine target column. `over.id` may be a column ID (string) or a card ID (number).
      let targetStatus: string;
      if (typeof over.id === 'string' && (KANBAN_STATUSES as readonly string[]).includes(over.id)) {
        targetStatus = over.id;
      } else {
        // Dropped on another card - find which column that card is in
        const overCard = prospects.find((p) => p.prospectId === over.id);
        if (!overCard) return;
        targetStatus = overCard.status;
      }

      if (card.status === targetStatus) return;

      onStatusChange(card.prospectId, card.status, targetStatus);
    },
    [prospects, onStatusChange],
  );

  const declinedProspects = columnData['DECLINED'] ?? [];

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <Box
          sx={{
            display: 'flex',
            gap: 1.5,
            overflowX: 'auto',
            pb: 2,
            minHeight: 400,
          }}
        >
          {KANBAN_STATUSES.map((status) => (
            <KanbanColumn
              key={status}
              status={status}
              prospects={columnData[status] ?? []}
              isLoading={isLoading}
              onCardClick={onCardClick}
            />
          ))}
        </Box>

        <DragOverlay>
          {activeCard ? (
            <Box sx={{ width: 280 }}>
              <ProspectCardContent prospect={activeCard} onClick={() => {}} isDragOverlay />
            </Box>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Archived / Declined section */}
      {declinedProspects.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Button
            size="small"
            startIcon={archivedOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            onClick={() => setArchivedOpen((prev) => !prev)}
            sx={{ mb: 1 }}
          >
            Archived ({declinedProspects.length})
          </Button>
          <Collapse in={archivedOpen}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {declinedProspects.map((p) => (
                <Box key={p.prospectId} sx={{ width: 280 }}>
                  <ProspectCardContent prospect={p} onClick={onCardClick} />
                </Box>
              ))}
            </Box>
          </Collapse>
        </Box>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// ListView
// ---------------------------------------------------------------------------

interface ListViewProps {
  prospects: ProspectListDto[];
  isLoading: boolean;
  totalCount: number;
  paginationModel: GridPaginationModel;
  sortModel: GridSortModel;
  onPaginationChange: (model: GridPaginationModel) => void;
  onSortChange: (model: GridSortModel) => void;
  onRowClick: (id: number) => void;
}

function ListView({
  prospects,
  isLoading,
  totalCount,
  paginationModel,
  sortModel,
  onPaginationChange,
  onSortChange,
  onRowClick,
}: ListViewProps) {
  const columns: GridColDef<ProspectListDto>[] = useMemo(
    () => [
      {
        field: 'opportunityTitle',
        headerName: 'Title',
        flex: 2,
        minWidth: 250,
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
        field: 'status',
        headerName: 'Status',
        width: 130,
        renderCell: (params) => <StatusChip status={STATUS_LABELS[params.value] ?? params.value} />,
      },
      {
        field: 'priority',
        headerName: 'Priority',
        width: 100,
        renderCell: (params) => {
          const val = params.value as string | null | undefined;
          if (!val) return '--';
          return (
            <Chip
              label={val}
              size="small"
              color={val === 'HIGH' ? 'error' : val === 'MEDIUM' ? 'warning' : 'default'}
            />
          );
        },
      },
      {
        field: 'goNoGoScore',
        headerName: 'Score',
        width: 80,
        align: 'center',
        headerAlign: 'center',
        valueFormatter: (value: number | null | undefined) =>
          value != null ? String(value) : '--',
      },
      {
        field: 'assignedToName',
        headerName: 'Assigned To',
        width: 140,
        valueFormatter: (value: string | null | undefined) => value ?? '--',
      },
      {
        field: 'estimatedValue',
        headerName: 'Value',
        width: 130,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params) => (
          <CurrencyDisplay value={params.value as number | null | undefined} compact />
        ),
      },
      {
        field: 'responseDeadline',
        headerName: 'Deadline',
        width: 160,
        renderCell: (params) => (
          <DeadlineCountdown deadline={params.value as string | null} />
        ),
      },
      {
        field: 'createdAt',
        headerName: 'Created',
        width: 120,
        valueFormatter: (value: string | null | undefined) => formatDate(value ?? null),
      },
    ],
    [],
  );

  const handleRowClick = useCallback(
    (params: GridRowParams<ProspectListDto>) => {
      onRowClick(params.row.prospectId);
    },
    [onRowClick],
  );

  return (
    <DataTable
      columns={columns}
      rows={prospects}
      loading={isLoading}
      rowCount={totalCount}
      paginationModel={paginationModel}
      onPaginationModelChange={onPaginationChange}
      sortModel={sortModel}
      onSortModelChange={onSortChange}
      onRowClick={handleRowClick}
      getRowId={(row: ProspectListDto) => row.prospectId}
      sx={{ minHeight: 400 }}
    />
  );
}

// ---------------------------------------------------------------------------
// ProspectPipelinePage
// ---------------------------------------------------------------------------

export default function ProspectPipelinePage() {
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // View toggle
  const [viewMode, setViewMode] = useState<ViewMode>('kanban');

  // Filter state
  const [filters, setFilters] = useState({
    myProspects: false,
    dueThisWeek: false,
    highPriority: false,
    status: '',
  });

  // Pagination/sort state for list view
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [sortModel, setSortModel] = useState<GridSortModel>([]);

  // Build search params
  const searchParams = useMemo<ProspectSearchParams>(() => {
    const params: ProspectSearchParams = {};

    if (filters.myProspects && user) {
      params.assignedTo = user.userId;
    }
    if (filters.highPriority) {
      params.priority = 'HIGH';
    }
    if (filters.status) {
      params.status = filters.status;
    }
    if (filters.dueThisWeek) {
      params.openOnly = true;
    }

    if (viewMode === 'kanban') {
      // Fetch all for kanban (reasonable page size to get everything)
      params.pageSize = 200;
      params.page = 1;
    } else {
      params.page = paginationModel.page + 1; // MUI 0-indexed -> API 1-indexed
      params.pageSize = paginationModel.pageSize;
      if (sortModel.length > 0) {
        params.sortBy = sortModel[0].field;
        params.sortDescending = sortModel[0].sort === 'desc';
      }
    }

    return params;
  }, [filters, user, viewMode, paginationModel, sortModel]);

  const { data, isLoading } = useProspectSearch(searchParams);
  const updateStatusMutation = useUpdateProspectStatus();

  const prospects = data?.items ?? [];
  const totalCount = data?.totalCount ?? 0;

  // Navigation
  const handleCardClick = useCallback(
    (id: number) => {
      navigate(`/prospects/${id}`);
    },
    [navigate],
  );

  // Status change with state machine validation + optimistic update
  const handleStatusChange = useCallback(
    (id: number, fromStatus: string, toStatus: string) => {
      if (!isValidTransition(fromStatus, toStatus)) {
        enqueueSnackbar(
          `Cannot move from ${STATUS_LABELS[fromStatus] ?? fromStatus} to ${STATUS_LABELS[toStatus] ?? toStatus}`,
          { variant: 'error' },
        );
        return;
      }

      // Optimistic update: patch the cache immediately
      const queryKey = queryKeys.prospects.list(searchParams as Record<string, unknown>);
      const previousData = queryClient.getQueryData(queryKey);

      queryClient.setQueryData(queryKey, (old: typeof data) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((p: ProspectListDto) =>
            p.prospectId === id ? { ...p, status: toStatus } : p,
          ),
        };
      });

      updateStatusMutation.mutate(
        { id, data: { newStatus: toStatus } },
        {
          onError: () => {
            // Revert optimistic update
            queryClient.setQueryData(queryKey, previousData);
            enqueueSnackbar('Failed to update status', { variant: 'error' });
          },
          onSuccess: () => {
            enqueueSnackbar(
              `Moved to ${STATUS_LABELS[toStatus] ?? toStatus}`,
              { variant: 'success' },
            );
          },
        },
      );
    },
    [enqueueSnackbar, updateStatusMutation, queryClient, searchParams, data],
  );

  // Filter handlers
  const toggleMyProspects = useCallback(() => {
    setFilters((prev) => ({ ...prev, myProspects: !prev.myProspects }));
  }, []);

  const toggleDueThisWeek = useCallback(() => {
    setFilters((prev) => ({ ...prev, dueThisWeek: !prev.dueThisWeek }));
  }, []);

  const toggleHighPriority = useCallback(() => {
    setFilters((prev) => ({ ...prev, highPriority: !prev.highPriority }));
  }, []);

  const handleStatusFilter = useCallback((status: string) => {
    setFilters((prev) => ({ ...prev, status }));
  }, []);

  // Empty state
  if (!isLoading && totalCount === 0) {
    return (
      <Box>
        <PageHeader title="Prospect Pipeline" subtitle="Track and manage your bid pipeline" />
        <FilterBar
          filters={filters}
          onToggleMyProspects={toggleMyProspects}
          onToggleDueThisWeek={toggleDueThisWeek}
          onToggleHighPriority={toggleHighPriority}
          onStatusChange={handleStatusFilter}
        />
        <EmptyState
          title="No prospects yet"
          message="Start by searching for opportunities and tracking them as prospects."
          action={
            <Button variant="contained" onClick={() => navigate('/opportunities')}>
              Search Opportunities
            </Button>
          }
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Prospect Pipeline"
        subtitle="Track and manage your bid pipeline"
        actions={
          <IconButton
            onClick={() => setViewMode((prev) => (prev === 'kanban' ? 'list' : 'kanban'))}
            title={viewMode === 'kanban' ? 'Switch to list view' : 'Switch to kanban view'}
          >
            {viewMode === 'kanban' ? <ViewListIcon /> : <ViewColumnIcon />}
          </IconButton>
        }
      />

      <FilterBar
        filters={filters}
        onToggleMyProspects={toggleMyProspects}
        onToggleDueThisWeek={toggleDueThisWeek}
        onToggleHighPriority={toggleHighPriority}
        onStatusChange={handleStatusFilter}
      />

      {viewMode === 'kanban' ? (
        <KanbanView
          prospects={prospects}
          isLoading={isLoading}
          onCardClick={handleCardClick}
          onStatusChange={handleStatusChange}
        />
      ) : (
        <ListView
          prospects={prospects}
          isLoading={isLoading}
          totalCount={totalCount}
          paginationModel={paginationModel}
          sortModel={sortModel}
          onPaginationChange={setPaginationModel}
          onSortChange={setSortModel}
          onRowClick={handleCardClick}
        />
      )}
    </Box>
  );
}
