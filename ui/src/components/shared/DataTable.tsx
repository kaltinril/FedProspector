import { DataGrid } from '@mui/x-data-grid';
import type {
  GridColDef,
  GridColumnVisibilityModel,
  GridPaginationModel,
  GridSortModel,
  GridRowParams,
  GridSlotsComponent,
} from '@mui/x-data-grid';
import type { SxProps, Theme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import { EmptyState } from '@/components/shared/EmptyState';

interface DataTableProps<T extends Record<string, unknown> = Record<string, unknown>> {
  columns: GridColDef<T>[];
  rows: T[];
  loading?: boolean;
  rowCount?: number;
  paginationModel?: GridPaginationModel;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
  sortModel?: GridSortModel;
  onSortModelChange?: (model: GridSortModel) => void;
  onRowClick?: (params: GridRowParams<T>) => void;
  getRowId?: (row: T) => string | number;
  columnVisibilityModel?: GridColumnVisibilityModel;
  slots?: Partial<GridSlotsComponent>;
  sx?: SxProps<Theme>;
  'aria-label'?: string;
}

function NoRowsOverlay() {
  return <EmptyState title="No data" message="No records match your criteria." />;
}

export function DataTable<T extends Record<string, unknown> = Record<string, unknown>>({
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
  columnVisibilityModel,
  slots,
  sx,
  'aria-label': ariaLabel,
}: DataTableProps<T>) {
  return (
    <Box sx={{ width: '100%', overflowX: 'auto', ...sx }}>
      <DataGrid
        aria-label={ariaLabel ?? 'Data table'}
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
        columnVisibilityModel={columnVisibilityModel}
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
