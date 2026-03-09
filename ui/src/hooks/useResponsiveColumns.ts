import { useMemo } from 'react';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';
import type { GridColumnVisibilityModel } from '@mui/x-data-grid';

/**
 * Configuration for responsive column hiding.
 *
 * Each key is a column field name. The value is the minimum breakpoint at which
 * the column should be visible:
 *   - 'sm'  → visible at sm and above (hidden on xs)
 *   - 'md'  → visible at md and above (hidden below md)
 *   - 'lg'  → visible at lg and above (hidden below lg)
 *
 * Columns not listed are always visible.
 */
export type ResponsiveColumnConfig = Record<string, 'sm' | 'md' | 'lg'>;

/**
 * Hook that converts a responsive column config into a MUI DataGrid
 * columnVisibilityModel based on the current viewport width.
 *
 * @example
 * const responsiveConfig: ResponsiveColumnConfig = {
 *   departmentName: 'md',   // hidden below md
 *   popState: 'md',         // hidden below md
 *   naicsCode: 'lg',        // hidden below lg
 * };
 * const columnVisibility = useResponsiveColumns(responsiveConfig);
 * // Pass to DataTable: <DataTable columnVisibilityModel={columnVisibility} ... />
 */
export function useResponsiveColumns(
  config?: ResponsiveColumnConfig,
): GridColumnVisibilityModel | undefined {
  const theme = useTheme();
  const isSmUp = useMediaQuery(theme.breakpoints.up('sm'));
  const isMdUp = useMediaQuery(theme.breakpoints.up('md'));
  const isLgUp = useMediaQuery(theme.breakpoints.up('lg'));

  return useMemo(() => {
    if (!config || Object.keys(config).length === 0) return undefined;

    const model: GridColumnVisibilityModel = {};
    for (const [field, minBreakpoint] of Object.entries(config)) {
      switch (minBreakpoint) {
        case 'sm':
          model[field] = isSmUp;
          break;
        case 'md':
          model[field] = isMdUp;
          break;
        case 'lg':
          model[field] = isLgUp;
          break;
      }
    }
    return model;
  }, [config, isSmUp, isMdUp, isLgUp]);
}
