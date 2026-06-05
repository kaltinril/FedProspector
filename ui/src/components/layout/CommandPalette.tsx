import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Dialog from '@mui/material/Dialog';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import { useAuth } from '@/auth/useAuth';
import { getNavSections } from '@/components/layout/navConfig';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

interface PaletteEntry {
  label: string;
  group: string;
  route: string;
  icon: React.ReactElement;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { isSystemAdmin } = useAuth();
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const entries = useMemo<PaletteEntry[]>(() => {
    return getNavSections(isSystemAdmin).flatMap((section) =>
      section.items.map((item) => ({
        label: item.label,
        group: section.title,
        route: item.route,
        icon: item.icon,
      })),
    );
  }, [isSystemAdmin]);

  const filtered = useMemo<PaletteEntry[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (entry) =>
        entry.label.toLowerCase().includes(q) || entry.group.toLowerCase().includes(q),
    );
  }, [entries, query]);

  // Clamp the highlighted row to the current result set at render time so we
  // never need to write state from an effect when the filter changes.
  const safeIndex = filtered.length === 0 ? 0 : Math.min(activeIndex, filtered.length - 1);

  // Scroll the highlighted row into view as the user arrows through results.
  useEffect(() => {
    const node = listRef.current?.querySelector<HTMLElement>(`[data-index="${safeIndex}"]`);
    node?.scrollIntoView({ block: 'nearest' });
  }, [safeIndex]);

  function reset() {
    setQuery('');
    setActiveIndex(0);
  }

  function close() {
    reset();
    onClose();
  }

  function go(route: string) {
    close();
    navigate(route);
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex(filtered.length === 0 ? 0 : (safeIndex + 1) % filtered.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex(
        filtered.length === 0 ? 0 : (safeIndex - 1 + filtered.length) % filtered.length,
      );
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const entry = filtered[safeIndex];
      if (entry) {
        go(entry.route);
      }
    }
    // Escape is handled by the Dialog's onClose.
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      fullWidth
      maxWidth="sm"
      slotProps={{
        paper: {
          sx: {
            position: 'fixed',
            top: { xs: 16, sm: 80 },
            m: 0,
            width: '100%',
            maxWidth: 560,
          },
        },
      }}
    >
      <Box sx={{ p: 1.5, pb: 1 }}>
        <TextField
          autoFocus
          fullWidth
          size="small"
          placeholder="Jump to page…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIndex(0);
          }}
          onKeyDown={handleKeyDown}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchOutlined fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
      </Box>
      <List ref={listRef} dense disablePadding sx={{ maxHeight: 360, overflowY: 'auto', pb: 1 }}>
        {filtered.length === 0 ? (
          <ListItem>
            <ListItemText
              primary="No matching pages"
              slotProps={{ primary: { sx: { color: 'text.secondary', fontSize: '0.875rem' } } }}
            />
          </ListItem>
        ) : (
          filtered.map((entry, index) => (
            <ListItem key={entry.route} disablePadding>
              <ListItemButton
                data-index={index}
                selected={index === safeIndex}
                onClick={() => go(entry.route)}
                onMouseMove={() => setActiveIndex(index)}
                sx={{ px: 2 }}
              >
                <ListItemIcon sx={{ minWidth: 36, color: 'text.secondary' }}>
                  {entry.icon}
                </ListItemIcon>
                <ListItemText
                  primary={entry.label}
                  slotProps={{ primary: { sx: { fontSize: '0.875rem' } } }}
                />
                <Typography variant="caption" sx={{ color: 'text.secondary', ml: 1 }}>
                  {entry.group}
                </Typography>
              </ListItemButton>
            </ListItem>
          ))
        )}
      </List>
    </Dialog>
  );
}
