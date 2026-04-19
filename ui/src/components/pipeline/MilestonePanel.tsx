import { useState } from 'react';
import { useSnackbar } from 'notistack';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import AddIcon from '@mui/icons-material/Add';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';

import { EmptyState } from '@/components/shared/EmptyState';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';

import {
  useProspectMilestones,
  useCreateMilestone,
  useUpdateMilestone,
  useDeleteMilestone,
  useGenerateTimeline,
} from '@/queries/usePipeline';
import { formatDate } from '@/utils/dateFormatters';
import type { ProspectMilestoneDto } from '@/types/pipeline';

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

const TEMPLATES = [
  { value: 'standard_rfp', label: 'Standard RFP' },
  { value: 'quick_quote', label: 'Quick Quote' },
  { value: 'large_proposal', label: 'Large Proposal' },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MilestonePanelProps {
  prospectId: number;
  responseDeadline?: string | null;
}

// ---------------------------------------------------------------------------
// MilestonePanel
// ---------------------------------------------------------------------------

export function MilestonePanel({ prospectId, responseDeadline }: MilestonePanelProps) {
  const { enqueueSnackbar } = useSnackbar();

  const { data: milestones, isLoading, isError, refetch } = useProspectMilestones(prospectId);
  const createMutation = useCreateMilestone();
  const updateMutation = useUpdateMilestone();
  const deleteMutation = useDeleteMilestone();
  const generateMutation = useGenerateTimeline();

  // Add dialog state
  const [addOpen, setAddOpen] = useState(false);
  const [addName, setAddName] = useState('');
  const [addDate, setAddDate] = useState('');
  const [addNotes, setAddNotes] = useState('');

  // Edit dialog state
  const [editItem, setEditItem] = useState<ProspectMilestoneDto | null>(null);
  const [editName, setEditName] = useState('');
  const [editDate, setEditDate] = useState('');
  const [editNotes, setEditNotes] = useState('');

  // Delete confirm
  const [deleteItem, setDeleteItem] = useState<ProspectMilestoneDto | null>(null);

  // Generate dialog
  const [genOpen, setGenOpen] = useState(false);
  const [genTemplate, setGenTemplate] = useState('standard_rfp');

  // ------ Handlers ------

  const handleAdd = () => {
    if (!addName.trim() || !addDate) return;
    createMutation.mutate(
      {
        prospectId,
        data: {
          milestoneName: addName.trim(),
          targetDate: addDate,
          notes: addNotes.trim() || undefined,
        },
      },
      {
        onSuccess: () => {
          setAddOpen(false);
          setAddName('');
          setAddDate('');
          setAddNotes('');
          enqueueSnackbar('Milestone added', { variant: 'success' });
        },
        onError: () => enqueueSnackbar('Failed to add milestone', { variant: 'error' }),
      },
    );
  };

  const handleToggleComplete = (milestone: ProspectMilestoneDto) => {
    const isNowCompleted = !milestone.isCompleted;
    updateMutation.mutate(
      {
        milestoneId: milestone.prospectMilestoneId,
        prospectId,
        data: {
          isCompleted: isNowCompleted,
          completedDate: isNowCompleted ? new Date().toISOString().split('T')[0] : null,
        },
      },
      {
        onError: () => enqueueSnackbar('Failed to update milestone', { variant: 'error' }),
      },
    );
  };

  const openEdit = (milestone: ProspectMilestoneDto) => {
    setEditItem(milestone);
    setEditName(milestone.milestoneName);
    setEditDate(milestone.targetDate);
    setEditNotes(milestone.notes ?? '');
  };

  const handleEdit = () => {
    if (!editItem || !editName.trim() || !editDate) return;
    updateMutation.mutate(
      {
        milestoneId: editItem.prospectMilestoneId,
        prospectId,
        data: {
          milestoneName: editName.trim(),
          targetDate: editDate,
          notes: editNotes.trim() || null,
        },
      },
      {
        onSuccess: () => {
          setEditItem(null);
          enqueueSnackbar('Milestone updated', { variant: 'success' });
        },
        onError: () => enqueueSnackbar('Failed to update milestone', { variant: 'error' }),
      },
    );
  };

  const handleDelete = () => {
    if (!deleteItem) return;
    deleteMutation.mutate(
      { milestoneId: deleteItem.prospectMilestoneId, prospectId },
      {
        onSuccess: () => {
          setDeleteItem(null);
          enqueueSnackbar('Milestone deleted', { variant: 'success' });
        },
        onError: () => enqueueSnackbar('Failed to delete milestone', { variant: 'error' }),
      },
    );
  };

  const handleGenerate = () => {
    if (!responseDeadline) {
      enqueueSnackbar('No response deadline set on this prospect', { variant: 'warning' });
      return;
    }
    const deadlineDate = responseDeadline.split('T')[0];
    generateMutation.mutate(
      {
        prospectId,
        data: {
          responseDeadline: deadlineDate,
          templateName: genTemplate,
        },
      },
      {
        onSuccess: () => {
          setGenOpen(false);
          enqueueSnackbar('Timeline generated', { variant: 'success' });
        },
        onError: () => enqueueSnackbar('Failed to generate timeline', { variant: 'error' }),
      },
    );
  };

  // ------ Render ------

  if (isLoading) return <LoadingState message="Loading milestones..." />;
  if (isError) return <ErrorState title="Failed to load milestones" onRetry={() => refetch()} />;

  const sortedMilestones = [...(milestones ?? [])].sort(
    (a, b) => a.sortOrder - b.sortOrder || a.targetDate.localeCompare(b.targetDate),
  );

  return (
    <Box>
      {/* Actions */}
      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={() => setAddOpen(true)}
        >
          Add Milestone
        </Button>
        <Button
          variant="outlined"
          size="small"
          startIcon={<AutoFixHighIcon />}
          onClick={() => setGenOpen(true)}
          disabled={!responseDeadline}
        >
          Generate Timeline
        </Button>
      </Box>
      {/* Milestone list */}
      {sortedMilestones.length === 0 ? (
        <EmptyState
          title="No Milestones"
          message="Add milestones manually or generate a timeline from a template."
        />
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ minWidth: 600 }}>
            <TableHead>
              <TableRow>
                <TableCell width={50}>Done</TableCell>
                <TableCell>Milestone</TableCell>
                <TableCell width={130}>Target Date</TableCell>
                <TableCell width={130}>Completed</TableCell>
                <TableCell>Notes</TableCell>
                <TableCell width={80} />
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedMilestones.map((m) => {
                const overdue =
                  !m.isCompleted && new Date(m.targetDate) < new Date();
                return (
                  <TableRow
                    key={m.prospectMilestoneId}
                    sx={{
                      textDecoration: m.isCompleted ? 'line-through' : undefined,
                      opacity: m.isCompleted ? 0.7 : 1,
                    }}
                  >
                    <TableCell>
                      <Checkbox
                        checked={m.isCompleted}
                        onChange={() => handleToggleComplete(m)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{
                        fontWeight: 500
                      }}>
                        {m.milestoneName}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Typography variant="body2">
                          {formatDate(m.targetDate)}
                        </Typography>
                        {overdue && (
                          <Chip label="Overdue" size="small" color="error" />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{
                        color: "text.secondary"
                      }}>
                        {m.completedDate ? formatDate(m.completedDate) : '--'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{
                        color: "text.secondary"
                      }}>
                        {m.notes ?? '--'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        <IconButton
                          size="small"
                          onClick={() => openEdit(m)}
                          aria-label="Edit milestone"
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => setDeleteItem(m)}
                          aria-label="Delete milestone"
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {/* Add Dialog */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Milestone</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            label="Milestone Name"
            fullWidth
            value={addName}
            onChange={(e) => setAddName(e.target.value)}
            sx={{ mt: 1, mb: 2 }}
          />
          <TextField
            label="Target Date"
            type="date"
            fullWidth
            value={addDate}
            onChange={(e) => setAddDate(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Notes (optional)"
            fullWidth
            multiline
            minRows={2}
            value={addNotes}
            onChange={(e) => setAddNotes(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleAdd}
            disabled={!addName.trim() || !addDate || createMutation.isPending}
          >
            Add
          </Button>
        </DialogActions>
      </Dialog>
      {/* Edit Dialog */}
      <Dialog open={!!editItem} onClose={() => setEditItem(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Milestone</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            label="Milestone Name"
            fullWidth
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            sx={{ mt: 1, mb: 2 }}
          />
          <TextField
            label="Target Date"
            type="date"
            fullWidth
            value={editDate}
            onChange={(e) => setEditDate(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Notes"
            fullWidth
            multiline
            minRows={2}
            value={editNotes}
            onChange={(e) => setEditNotes(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditItem(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleEdit}
            disabled={!editName.trim() || !editDate || updateMutation.isPending}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
      {/* Generate Timeline Dialog */}
      <Dialog open={genOpen} onClose={() => setGenOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Generate Timeline</DialogTitle>
        <DialogContent>
          <Typography
            variant="body2"
            sx={{
              color: "text.secondary",
              mb: 2
            }}>
            Select a template to generate milestones based on the response deadline
            ({responseDeadline ? formatDate(responseDeadline) : 'not set'}).
          </Typography>
          <TextField
            select
            label="Template"
            fullWidth
            value={genTemplate}
            onChange={(e) => setGenTemplate(e.target.value)}
          >
            {TEMPLATES.map((t) => (
              <MenuItem key={t.value} value={t.value}>
                {t.label}
              </MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setGenOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleGenerate}
            disabled={generateMutation.isPending}
          >
            Generate
          </Button>
        </DialogActions>
      </Dialog>
      {/* Delete Confirm */}
      <ConfirmDialog
        open={!!deleteItem}
        title="Delete Milestone"
        message={`Delete "${deleteItem?.milestoneName ?? ''}"? This action cannot be undone.`}
        severity="error"
        confirmText="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteItem(null)}
        loading={deleteMutation.isPending}
      />
    </Box>
  );
}
