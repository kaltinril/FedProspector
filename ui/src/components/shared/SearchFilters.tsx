import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Autocomplete from '@mui/material/Autocomplete';
import Paper from '@mui/material/Paper';
import SearchIcon from '@mui/icons-material/Search';
import ClearAllIcon from '@mui/icons-material/ClearAll';

interface FilterOption {
  value: string;
  label: string;
}

interface FilterConfig {
  key: string;
  label: string;
  type: 'text' | 'select' | 'multiSelect' | 'date' | 'dateRange';
  options?: FilterOption[];
}

interface SearchFiltersProps {
  filters: FilterConfig[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  onClear: () => void;
  onSearch: () => void;
}

export type { FilterConfig, FilterOption, SearchFiltersProps };

function getActiveFilters(
  filters: FilterConfig[],
  values: Record<string, unknown>,
): { key: string; label: string; display: string }[] {
  const active: { key: string; label: string; display: string }[] = [];
  for (const filter of filters) {
    const val = values[filter.key];
    if (val == null || val === '') continue;

    if (filter.type === 'multiSelect' && Array.isArray(val) && val.length > 0) {
      const labels = (val as string[])
        .map((v) => filter.options?.find((o) => o.value === v)?.label ?? v)
        .join(', ');
      active.push({ key: filter.key, label: filter.label, display: labels });
    } else if (filter.type === 'dateRange' && typeof val === 'object' && val !== null) {
      const range = val as { start?: string; end?: string };
      if (range.start || range.end) {
        const display = [range.start, range.end].filter(Boolean).join(' - ');
        active.push({ key: filter.key, label: filter.label, display });
      }
    } else if (filter.type === 'select') {
      const display = filter.options?.find((o) => o.value === val)?.label ?? String(val);
      active.push({ key: filter.key, label: filter.label, display });
    } else if (typeof val === 'string' && val.length > 0) {
      active.push({ key: filter.key, label: filter.label, display: String(val) });
    }
  }
  return active;
}

export function SearchFilters({
  filters,
  values,
  onChange,
  onClear,
  onSearch,
}: SearchFiltersProps) {
  const activeFilters = getActiveFilters(filters, values);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onSearch();
    }
  };

  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 2,
          alignItems: 'flex-end',
        }}
        onKeyDown={handleKeyDown}
      >
        {filters.map((filter) => {
          switch (filter.type) {
            case 'text':
              return (
                <TextField
                  key={filter.key}
                  label={filter.label}
                  value={(values[filter.key] as string) ?? ''}
                  onChange={(e) => onChange(filter.key, e.target.value)}
                  size="small"
                  sx={{ minWidth: 200 }}
                />
              );

            case 'select':
              return (
                <TextField
                  key={filter.key}
                  label={filter.label}
                  value={(values[filter.key] as string) ?? ''}
                  onChange={(e) => onChange(filter.key, e.target.value)}
                  select
                  size="small"
                  sx={{ minWidth: 180 }}
                >
                  <MenuItem value="">All</MenuItem>
                  {filter.options?.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </TextField>
              );

            case 'multiSelect':
              return (
                <Autocomplete
                  key={filter.key}
                  multiple
                  options={filter.options ?? []}
                  getOptionLabel={(opt) => opt.label}
                  value={
                    filter.options?.filter((o) =>
                      ((values[filter.key] as string[]) ?? []).includes(o.value),
                    ) ?? []
                  }
                  onChange={(_e, newValue) =>
                    onChange(
                      filter.key,
                      newValue.map((v) => v.value),
                    )
                  }
                  renderInput={(params) => (
                    <TextField {...params} label={filter.label} size="small" />
                  )}
                  size="small"
                  sx={{ minWidth: 250 }}
                />
              );

            case 'date':
              return (
                <TextField
                  key={filter.key}
                  label={filter.label}
                  type="date"
                  value={(values[filter.key] as string) ?? ''}
                  onChange={(e) => onChange(filter.key, e.target.value)}
                  size="small"
                  slotProps={{ inputLabel: { shrink: true } }}
                  sx={{ minWidth: 170 }}
                />
              );

            case 'dateRange': {
              const range = (values[filter.key] as { start?: string; end?: string }) ?? {};
              return (
                <Box key={filter.key} sx={{ display: 'flex', gap: 1 }}>
                  <TextField
                    label={`${filter.label} From`}
                    type="date"
                    value={range.start ?? ''}
                    onChange={(e) =>
                      onChange(filter.key, { ...range, start: e.target.value })
                    }
                    size="small"
                    slotProps={{ inputLabel: { shrink: true } }}
                    sx={{ minWidth: 155 }}
                  />
                  <TextField
                    label={`${filter.label} To`}
                    type="date"
                    value={range.end ?? ''}
                    onChange={(e) =>
                      onChange(filter.key, { ...range, end: e.target.value })
                    }
                    size="small"
                    slotProps={{ inputLabel: { shrink: true } }}
                    sx={{ minWidth: 155 }}
                  />
                </Box>
              );
            }

            default:
              return null;
          }
        })}

        <Button
          variant="contained"
          startIcon={<SearchIcon />}
          onClick={onSearch}
          size="medium"
        >
          Search
        </Button>
        <Button
          variant="text"
          startIcon={<ClearAllIcon />}
          onClick={onClear}
          size="medium"
        >
          Clear All
        </Button>
      </Box>

      {activeFilters.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
          {activeFilters.map((af) => (
            <Chip
              key={af.key}
              label={`${af.label}: ${af.display}`}
              size="small"
              onDelete={() => {
                const filter = filters.find((f) => f.key === af.key);
                if (filter?.type === 'multiSelect') {
                  onChange(af.key, []);
                } else if (filter?.type === 'dateRange') {
                  onChange(af.key, { start: '', end: '' });
                } else {
                  onChange(af.key, '');
                }
              }}
            />
          ))}
        </Box>
      )}
    </Paper>
  );
}
