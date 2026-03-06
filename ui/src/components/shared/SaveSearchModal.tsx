import { useState } from 'react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import { useSnackbar } from 'notistack';
import { createSavedSearch } from '@/api/savedSearches';

interface SaveSearchModalProps {
  open: boolean;
  onClose: () => void;
  filterCriteria: Record<string, unknown>;
}

export function SaveSearchModal({ open, onClose, filterCriteria }: SaveSearchModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const { enqueueSnackbar } = useSnackbar();

  function handleClose() {
    setName('');
    setDescription('');
    setError('');
    onClose();
  }

  async function handleSave() {
    if (!name.trim()) {
      setError('Name is required');
      return;
    }

    setSaving(true);
    setError('');
    try {
      await createSavedSearch({
        searchName: name.trim(),
        description: description.trim() || undefined,
        filterCriteria: filterCriteria as never,
      });
      enqueueSnackbar('Search saved. Manage saved searches from the sidebar.', {
        variant: 'success',
      });
      handleClose();
    } catch {
      setError('Failed to save search. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Save Search</DialogTitle>
      <DialogContent>
        <TextField
          required
          margin="dense"
          label="Search Name"
          fullWidth
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={!!error && !name.trim()}
          helperText={!name.trim() && error ? error : undefined}
          slotProps={{ htmlInput: { maxLength: 100 } }}
        />
        <TextField
          margin="dense"
          label="Description (optional)"
          fullWidth
          multiline
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          slotProps={{ htmlInput: { maxLength: 500 } }}
        />
        {error && name.trim() && (
          <TextField
            error
            helperText={error}
            sx={{ mt: 1 }}
            fullWidth
            disabled
            variant="standard"
            slotProps={{ input: { sx: { display: 'none' } } }}
          />
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={saving}>
          Cancel
        </Button>
        <Button onClick={handleSave} variant="contained" disabled={saving}>
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
