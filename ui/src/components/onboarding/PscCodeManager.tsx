import { useState } from 'react';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';
import AddOutlined from '@mui/icons-material/AddOutlined';
import CircularProgress from '@mui/material/CircularProgress';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { usePscCodes, useAddPscCode, useDeletePscCode } from '@/queries/useOnboarding';
import { formatRelative } from '@/utils/dateFormatters';

export function PscCodeManager() {
  const { data: pscCodes, isLoading, isError, refetch } = usePscCodes();
  const addMutation = useAddPscCode();
  const deleteMutation = useDeletePscCode();
  const [newCode, setNewCode] = useState('');

  function handleAdd() {
    const code = newCode.trim().toUpperCase();
    if (!code) return;
    addMutation.mutate(code, {
      onSuccess: () => setNewCode(''),
    });
  }

  function handleDelete(id: number) {
    deleteMutation.mutate(id);
  }

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>
          PSC Codes
        </Typography>

        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
          <TextField
            label="PSC Code"
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
            size="small"
            placeholder="e.g. D302"
            inputProps={{ maxLength: 10 }}
            disabled={addMutation.isPending}
          />
          <Button
            variant="contained"
            size="small"
            onClick={handleAdd}
            disabled={!newCode.trim() || addMutation.isPending}
            startIcon={
              addMutation.isPending ? (
                <CircularProgress size={16} />
              ) : (
                <AddOutlined />
              )
            }
          >
            Add
          </Button>
        </Box>

        {(!pscCodes || pscCodes.length === 0) ? (
          <EmptyState
            title="No PSC Codes"
            message="Add Product/Service codes to improve opportunity matching by service category."
          />
        ) : (
          <List dense disablePadding>
            {pscCodes.map((psc) => (
              <ListItem
                key={psc.organizationPscId}
                disableGutters
                secondaryAction={
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => handleDelete(psc.organizationPscId)}
                    disabled={deleteMutation.isPending}
                    aria-label={`Delete PSC ${psc.pscCode}`}
                  >
                    <DeleteOutlined fontSize="small" />
                  </IconButton>
                }
              >
                <ListItemText
                  primary={psc.pscCode}
                  secondary={psc.addedAt ? `Added ${formatRelative(psc.addedAt)}` : undefined}
                />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
}
