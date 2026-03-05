import { DataGrid } from '@mui/x-data-grid';
import type {
  GridColDef,
  GridPaginationModel,
  GridSortModel,
  GridRowParams,
  GridSlotsComponent,
} from '@mui/x-data-grid';
import type { SxProps, Theme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import { EmptyState } from '@/components/shared/EmptyState';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRow = any;

interface DataTableProps {
  columns: GridColDef<AnyRow>[];
  rows: AnyRow[];
  loading?: boolean;
  rowCount?: number;
  paginationModel?: GridPaginationModel;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
  sortModel?: GridSortModel;
  onSortModelChange?: (model: GridSortModel) => void;
  onRowClick?: (params: GridRowParams<AnyRow>) => void;
  getRowId?: (row: AnyRow) => string | number;
  slots?: Partial<GridSlotsComponent>;
  sx?: SxProps<Theme>;
}

function NoRowsOverlay() {
  return <EmptyState title="No data" message="No records match your criteria." />;
}

export function DataTable({
  columns,
  rows,
  loading = false,
  rowCount,
  paginationModel,
  onPaginationModelChange,
  sortModel,
  onSortModelChange,
  onRowClick,
  getRowId,
  slots,
  sx,
}: DataTableProps) {
  return (
    <Box sx={{ width: '100%', ...sx }}>
      <DataGrid
        columns={columns}
        rows={rows}
        loading={loading}
        rowCount={rowCount}
        paginationModel={paginationModel}
        onPaginationModelChange={onPaginationModelChange}
        sortModel={sortModel}
        onSortModelChange={onSortModelChange}
        onRowClick={onRowClick}
        getRowId={getRowId}
        paginationMode={rowCount != null ? 'server' : 'client'}
        sortingMode={onSortModelChange ? 'server' : 'client'}
        pageSizeOptions={[10, 25, 50, 100]}
        disableColumnFilter
        disableRowSelectionOnClick
        autoHeight
        slots={{
          noRowsOverlay: NoRowsOverlay,
          ...slots,
        }}
        sx={{
          border: 0,
          '& .MuiDataGrid-row:nth-of-type(even)': {
            bgcolor: 'action.hover',
          },
          '& .MuiDataGrid-row:hover': {
            bgcolor: 'action.selected',
          },
          '& .MuiDataGrid-columnHeaders': {
            bgcolor: 'background.default',
          },
        }}
      />
    </Box>
  );
}
