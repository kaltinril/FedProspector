import { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';

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
import { useSnackbar } from 'notistack';
import { BackToSearch } from '@/components/shared/BackToSearch';
import { PageHeader } from '@/components/shared/PageHeader';
import { StatusChip } from '@/components/shared/StatusChip';
import { DeadlineCountdown } from '@/components/shared/DeadlineCountdown';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import {
  useProposalSearch,
  useUpdateProposal,
  useCreateMilestone,
  useUpdateMilestone,
  useAddDocument,
} from '@/queries/useProposals';
import { formatDate } from '@/utils/dateFormatters';

import type {
  ProposalDetailDto,
  ProposalMilestoneDto,
  ProposalDocumentDto,
} from '@/types/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PROPOSAL_STATUSES = ['DRAFT', 'IN_PROGRESS', 'SUBMITTED', 'AWARDED', 'REJECTED'];

const MILESTONE_STATUSES = ['PENDING', 'IN_PROGRESS', 'COMPLETED'] as const;

const DOCUMENT_TYPES = [
  'PROPOSAL',
  'TECHNICAL_VOLUME',
  'COST_VOLUME',
  'PAST_PERFORMANCE',
  'MANAGEMENT_VOLUME',
  'SUBCONTRACTING_PLAN',
  'SUPPORTING',
  'OTHER',
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function nextMilestoneStatus(current: string): string {
  const idx = MILESTONE_STATUSES.indexOf(current as typeof MILESTONE_STATUSES[number]);
  if (idx < 0 || idx >= MILESTONE_STATUSES.length - 1) return current;
  return MILESTONE_STATUSES[idx + 1];
}

// ---------------------------------------------------------------------------
// Section 1: Edit Proposal
// ---------------------------------------------------------------------------

function EditProposalSection({ proposal }: { proposal: ProposalDetailDto }) {
  const updateProposal = useUpdateProposal();
  const { enqueueSnackbar } = useSnackbar();

  const [status, setStatus] = useState(proposal.proposalStatus);
  const [estimatedValue, setEstimatedValue] = useState(
    proposal.estimatedValue?.toString() ?? '',
  );
  const [winProbability, setWinProbability] = useState(
    proposal.winProbabilityPct?.toString() ?? '',
  );
  const [lessonsLearned, setLessonsLearned] = useState(
    proposal.lessonsLearned ?? '',
  );

  const handleSave = () => {
    updateProposal.mutate(
      {
        id: proposal.proposalId,
        data: {
          status,
          estimatedValue: estimatedValue ? Number(estimatedValue) : null,
          winProbabilityPct: winProbability ? Number(winProbability) : null,
          lessonsLearned: lessonsLearned || null,
        },
      },
      {
        onSuccess: () => {
          enqueueSnackbar('Proposal updated', { variant: 'success' });
        },
        onError: () => {
          enqueueSnackbar('Failed to update proposal', { variant: 'error' });
        },
      },
    );
  };

  return (
    <Paper variant="outlined" sx={{ p: 3 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Edit Proposal
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            select
            label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            size="small"
            sx={{ minWidth: 180 }}
          >
            {PROPOSAL_STATUSES.map((s) => (
              <MenuItem key={s} value={s}>
                {s.replace('_', ' ')}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Estimated Value"
            type="number"
            value={estimatedValue}
            onChange={(e) => setEstimatedValue(e.target.value)}
            size="small"
            sx={{ minWidth: 180 }}
          />
          <TextField
            label="Win Probability %"
            type="number"
            value={winProbability}
            onChange={(e) => setWinProbability(e.target.value)}
            size="small"
            sx={{ minWidth: 150 }}
            slotProps={{ htmlInput: { min: 0, max: 100 } }}
          />
        </Box>
        <TextField
          label="Lessons Learned"
          value={lessonsLearned}
          onChange={(e) => setLessonsLearned(e.target.value)}
          multiline
          minRows={3}
          size="small"
        />
        <Box>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={updateProposal.isPending}
          >
            {updateProposal.isPending ? 'Saving...' : 'Save'}
          </Button>
        </Box>
      </Box>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Section 2: Milestone Tracker
// ---------------------------------------------------------------------------

function MilestoneTrackerSection({ proposal }: { proposal: ProposalDetailDto }) {
  const createMilestone = useCreateMilestone();
  const updateMilestoneM = useUpdateMilestone();
  const { enqueueSnackbar } = useSnackbar();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDueDate, setNewDueDate] = useState('');
  const [newAssignedTo, setNewAssignedTo] = useState('');

  const handleAddMilestone = () => {
    if (!newDueDate) return;
    createMilestone.mutate(
      {
        proposalId: proposal.proposalId,
        data: {
          title: newName || null,
          dueDate: newDueDate,
          assignedTo: newAssignedTo ? Number(newAssignedTo) : null,
        },
      },
      {
        onSuccess: () => {
          setDialogOpen(false);
          setNewName('');
          setNewDueDate('');
          setNewAssignedTo('');
          enqueueSnackbar('Milestone added', { variant: 'success' });
        },
        onError: () => {
          enqueueSnackbar('Failed to add milestone', { variant: 'error' });
        },
      },
    );
  };

  const handleStatusCycle = (milestone: ProposalMilestoneDto) => {
    const next = nextMilestoneStatus(milestone.status);
    if (next === milestone.status) return;
    updateMilestoneM.mutate(
      {
        proposalId: proposal.proposalId,
        milestoneId: milestone.milestoneId,
        data: {
          status: next,
          completedDate: next === 'COMPLETED' ? new Date().toISOString() : null,
        },
      },
      {
        onError: () => {
          enqueueSnackbar('Failed to update milestone status', { variant: 'error' });
        },
      },
    );
  };

  const milestoneStatusColor = (status: string): 'default' | 'warning' | 'success' | 'info' => {
    switch (status) {
      case 'COMPLETED':
        return 'success';
      case 'IN_PROGRESS':
        return 'info';
      default:
        return 'default';
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Milestone Tracker</Typography>
        <Button startIcon={<AddIcon />} size="small" onClick={() => setDialogOpen(true)}>
          Add Milestone
        </Button>
      </Box>

      {proposal.milestones.length === 0 ? (
        <EmptyState title="No milestones" message="Add milestones to track proposal progress." />
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Due Date</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Completed</TableCell>
                <TableCell>Assigned To</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {proposal.milestones.map((m) => (
                <TableRow key={m.milestoneId}>
                  <TableCell>{m.milestoneName}</TableCell>
                  <TableCell>{formatDate(m.dueDate)}</TableCell>
                  <TableCell>
                    <Chip
                      label={m.status.replace('_', ' ')}
                      size="small"
                      color={milestoneStatusColor(m.status)}
                      onClick={() => handleStatusCycle(m)}
                      sx={{ cursor: 'pointer' }}
                    />
                  </TableCell>
                  <TableCell>{formatDate(m.completedDate)}</TableCell>
                  <TableCell>{m.assignedTo ?? '--'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Add Milestone Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Milestone</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField
            label="Name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            size="small"
            sx={{ mt: 1 }}
          />
          <TextField
            label="Due Date"
            type="date"
            value={newDueDate}
            onChange={(e) => setNewDueDate(e.target.value)}
            size="small"
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            label="Assigned To (User ID)"
            type="number"
            value={newAssignedTo}
            onChange={(e) => setNewAssignedTo(e.target.value)}
            size="small"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleAddMilestone}
            disabled={!newDueDate || createMilestone.isPending}
          >
            {createMilestone.isPending ? 'Adding...' : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Section 3: Document Registry
// ---------------------------------------------------------------------------

function DocumentRegistrySection({ proposal }: { proposal: ProposalDetailDto }) {
  const addDocument = useAddDocument();
  const { enqueueSnackbar } = useSnackbar();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [docName, setDocName] = useState('');
  const [docType, setDocType] = useState('');
  const [docSize, setDocSize] = useState('');

  const handleAddDocument = () => {
    addDocument.mutate(
      {
        proposalId: proposal.proposalId,
        data: {
          fileName: docName || null,
          documentType: docType || null,
          fileSizeBytes: docSize ? Number(docSize) : null,
        },
      },
      {
        onSuccess: () => {
          setDialogOpen(false);
          setDocName('');
          setDocType('');
          setDocSize('');
          enqueueSnackbar('Document added', { variant: 'success' });
        },
        onError: () => {
          enqueueSnackbar('Failed to add document', { variant: 'error' });
        },
      },
    );
  };

  return (
    <Paper variant="outlined" sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Document Registry</Typography>
        <Button startIcon={<AddIcon />} size="small" onClick={() => setDialogOpen(true)}>
          Add Document
        </Button>
      </Box>
      {proposal.documents.length === 0 ? (
        <EmptyState title="No documents" message="Add document metadata to track proposal artifacts." />
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Document Name</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Upload Date</TableCell>
                <TableCell>Uploaded By</TableCell>
                <TableCell align="right">File Size</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {proposal.documents.map((d: ProposalDocumentDto) => (
                <TableRow key={d.documentId}>
                  <TableCell>{d.fileName}</TableCell>
                  <TableCell>{d.documentType}</TableCell>
                  <TableCell>{formatDate(d.uploadedAt)}</TableCell>
                  <TableCell>{d.uploadedBy ?? '--'}</TableCell>
                  <TableCell align="right">{formatFileSize(d.fileSizeBytes)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {/* Add Document Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Document</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField
            label="Document Name"
            value={docName}
            onChange={(e) => setDocName(e.target.value)}
            size="small"
            sx={{ mt: 1 }}
          />
          <TextField
            select
            label="Document Type"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            size="small"
          >
            {DOCUMENT_TYPES.map((t) => (
              <MenuItem key={t} value={t}>
                {t.replace(/_/g, ' ')}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="File Size (bytes)"
            type="number"
            value={docSize}
            onChange={(e) => setDocSize(e.target.value)}
            size="small"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleAddDocument}
            disabled={addDocument.isPending}
          >
            {addDocument.isPending ? 'Adding...' : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Section 4: Lessons Learned (read-only display)
// ---------------------------------------------------------------------------

function LessonsLearnedSection({ proposal }: { proposal: ProposalDetailDto }) {
  return (
    <Paper variant="outlined" sx={{ p: 3 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Lessons Learned
      </Typography>
      {proposal.lessonsLearned ? (
        <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
          {proposal.lessonsLearned}
        </Typography>
      ) : (
        <Typography variant="body2" sx={{
          color: "text.secondary"
        }}>
          No lessons learned recorded yet. Use the Edit Proposal section above to add notes.
        </Typography>
      )}
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ProposalDetailPage() {
  const { id, proposalId } = useParams<{ id: string; proposalId: string }>();
  const prospectId = Number(id);
  const numericProposalId = Number(proposalId);

  // Fetch proposals for this prospect and find the one we want
  const {
    data: proposalsData,
    isLoading,
    isError,
    refetch,
  } = useProposalSearch({ prospectId, pageSize: 100 });

  const proposal = useMemo(() => {
    if (!proposalsData?.items) return null;
    return proposalsData.items.find((p) => p.proposalId === numericProposalId) ?? null;
  }, [proposalsData, numericProposalId]);

  if (isLoading) return <LoadingState message="Loading proposal..." />;

  if (isError) {
    return (
      <Box>
        <BackToSearch searchPath={`/prospects/${prospectId}`} label="Back to prospect" />
        <ErrorState
          title="Failed to load proposal"
          message="Could not connect to the server. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  if (!proposal) {
    return (
      <Box>
        <BackToSearch searchPath={`/prospects/${prospectId}`} label="Back to prospect" />
        <EmptyState
          title="Proposal not found"
          message="The requested proposal could not be found."
        />
      </Box>
    );
  }

  return (
    <Box>
      {/* Navigation */}
      <BackToSearch searchPath={`/prospects/${prospectId}`} label="Back to prospect" />
      {/* Breadcrumb */}
      <Typography
        variant="caption"
        sx={{
          color: "text.secondary",
          display: 'block',
          mb: 1
        }}>
        Dashboard &gt; Prospects &gt; {proposal.prospectTitle ?? `Prospect #${prospectId}`} &gt; Proposal #{proposal.proposalNumber ?? proposal.proposalId}
      </Typography>
      {/* Header */}
      <PageHeader
        title={`Proposal ${proposal.proposalNumber ?? `#${proposal.proposalId}`}`}
        subtitle={proposal.opportunityTitle ?? undefined}
      />
      {/* Summary bar */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'center' }}>
          <Box>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Status
            </Typography>
            <StatusChip status={proposal.proposalStatus} />
          </Box>
          <Box>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Submission Deadline
            </Typography>
            <DeadlineCountdown deadline={proposal.submissionDeadline ?? null} />
          </Box>
          <Box>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Estimated Value
            </Typography>
            <Typography variant="body1">
              <CurrencyDisplay value={proposal.estimatedValue} />
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Win Probability
            </Typography>
            <Typography variant="body1">
              {proposal.winProbabilityPct != null ? `${proposal.winProbabilityPct}%` : '--'}
            </Typography>
          </Box>
        </Box>
      </Paper>
      {/* Sections */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <EditProposalSection proposal={proposal} />
        <MilestoneTrackerSection proposal={proposal} />
        <DocumentRegistrySection proposal={proposal} />
        <LessonsLearnedSection proposal={proposal} />
      </Box>
    </Box>
  );
}
