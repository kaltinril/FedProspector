import { useState } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Alert from '@mui/material/Alert';
import Typography from '@mui/material/Typography';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import CircularProgress from '@mui/material/CircularProgress';

import { useImportUei } from '@/queries/useOnboarding';
import type { UeiImportResultDto } from '@/types/onboarding';

interface UeiImportDialogProps {
  open: boolean;
  onClose: () => void;
}

export function UeiImportDialog({ open, onClose }: UeiImportDialogProps) {
  const [uei, setUei] = useState('');
  const [result, setResult] = useState<UeiImportResultDto | null>(null);
  const importMutation = useImportUei();

  function handleImport() {
    if (!uei.trim()) return;
    setResult(null);
    importMutation.mutate(uei.trim(), {
      onSuccess: (data) => {
        setResult(data);
      },
    });
  }

  function handleClose() {
    setUei('');
    setResult(null);
    importMutation.reset();
    onClose();
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Import Organization Data from UEI</DialogTitle>
      <DialogContent>
        <Typography
          variant="body2"
          sx={{
            color: "text.secondary",
            mb: 2
          }}>
          Enter your Unique Entity Identifier (UEI) to auto-populate organization
          fields from SAM.gov registration data.
        </Typography>

        <TextField
          label="UEI"
          value={uei}
          onChange={(e) => setUei(e.target.value)}
          fullWidth
          placeholder="e.g. ABCD1234EFGH5"
          disabled={importMutation.isPending}
          sx={{ mb: 2 }}
          slotProps={{
            htmlInput: { maxLength: 13 }
          }}
        />

        {importMutation.isError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Import failed. Please verify the UEI and try again.
          </Alert>
        )}

        {result && !result.entityFound && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            No entity found for UEI &quot;{result.uei}&quot;. Please verify the UEI is correct.
          </Alert>
        )}

        {result && result.entityFound && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {result.message ?? 'Import completed successfully.'}
            <List dense disablePadding sx={{ mt: 1 }}>
              {result.fieldsPopulated.map((field) => (
                <ListItem key={field} disableGutters sx={{ py: 0 }}>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    <CheckCircleOutlined fontSize="small" color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary={field}
                    slotProps={{
                      primary: { variant: 'body2' }
                    }}
                  />
                </ListItem>
              ))}
              {result.naicsCodesImported > 0 && (
                <ListItem disableGutters sx={{ py: 0 }}>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    <CheckCircleOutlined fontSize="small" color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary={`${result.naicsCodesImported} NAICS code${result.naicsCodesImported !== 1 ? 's' : ''} imported`}
                    slotProps={{
                      primary: { variant: 'body2' }
                    }}
                  />
                </ListItem>
              )}
              {result.certificationsImported > 0 && (
                <ListItem disableGutters sx={{ py: 0 }}>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    <CheckCircleOutlined fontSize="small" color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary={`${result.certificationsImported} certification${result.certificationsImported !== 1 ? 's' : ''} imported`}
                    slotProps={{
                      primary: { variant: 'body2' }
                    }}
                  />
                </ListItem>
              )}
            </List>
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>
          {result?.entityFound ? 'Done' : 'Cancel'}
        </Button>
        {!result?.entityFound && (
          <Button
            variant="contained"
            onClick={handleImport}
            disabled={!uei.trim() || importMutation.isPending}
            startIcon={
              importMutation.isPending ? <CircularProgress size={16} /> : undefined
            }
          >
            Import
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
