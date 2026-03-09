import { useMemo, useState } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import { useSnackbar } from 'notistack';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import Link from '@mui/material/Link';
import Menu from '@mui/material/Menu';
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
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import DeleteIcon from '@mui/icons-material/Delete';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

import { PageHeader } from '@/components/shared/PageHeader';
import { BackToSearch } from '@/components/shared/BackToSearch';
import { TabbedDetailPage } from '@/components/shared/TabbedDetailPage';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { DeadlineCountdown } from '@/components/shared/DeadlineCountdown';
import { StatusChip } from '@/components/shared/StatusChip';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { EmptyState } from '@/components/shared/EmptyState';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import PWinGauge from '@/components/shared/PWinGauge';

import {
  useProspect,
  useUpdateProspectStatus,
  useAddProspectNote,
  useAddTeamMember,
  useRemoveTeamMember,
  useRecalculateScore,
} from '@/queries/useProspects';
import { useCreateProposal } from '@/queries/useProposals';
import { formatDate, formatRelative } from '@/utils/dateFormatters';
import { formatCurrency, formatPercent } from '@/utils/formatters';
import type {
  ProspectDetailDto,
  ProspectOpportunityDto,
  ScoreBreakdownDto,
  ProspectTeamMemberDto,
} from '@/types/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_TRANSITIONS: Record<string, string[]> = {
  NEW: ['REVIEWING', 'DECLINED'],
  REVIEWING: ['PURSUING', 'DECLINED'],
  PURSUING: ['BID_SUBMITTED', 'DECLINED'],
  BID_SUBMITTED: ['WON', 'LOST'],
};

const TERMINAL_STATUSES = ['DECLINED', 'WON', 'LOST'];

const PRIORITY_COLOR: Record<string, 'default' | 'warning' | 'error'> = {
  LOW: 'default',
  MEDIUM: 'warning',
  HIGH: 'error',
  CRITICAL: 'error',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildPoP(opp: ProspectOpportunityDto): string {
  const parts: string[] = [];
  if (opp.popState) parts.push(opp.popState);
  if (opp.popZip) parts.push(opp.popZip);
  if (opp.popCountry && opp.popCountry !== 'USA' && opp.popCountry !== 'US') {
    parts.push(opp.popCountry);
  }
  return parts.length > 0 ? parts.join(', ') : '--';
}

function scoreCategory(percentage: number): string {
  if (percentage >= 75) return 'High';
  if (percentage >= 50) return 'Medium';
  if (percentage >= 25) return 'Low';
  return 'VeryLow';
}

// ---------------------------------------------------------------------------
// Status Transition Dropdown
// ---------------------------------------------------------------------------

function StatusTransitionButton({
  prospectId,
  currentStatus,
}: {
  prospectId: number;
  currentStatus: string;
}) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const { enqueueSnackbar } = useSnackbar();
  const statusMutation = useUpdateProspectStatus();

  const nextStatuses = STATUS_TRANSITIONS[currentStatus] ?? [];
  const isTerminal = TERMINAL_STATUSES.includes(currentStatus);

  if (isTerminal || nextStatuses.length === 0) {
    return null;
  }

  const handleClick = (newStatus: string) => {
    setAnchorEl(null);
    statusMutation.mutate(
      { id: prospectId, data: { newStatus } },
      {
        onSuccess: () => {
          enqueueSnackbar(`Status updated to ${newStatus}`, { variant: 'success' });
        },
        onError: () => {
          enqueueSnackbar('Failed to update status', { variant: 'error' });
        },
      },
    );
  };

  return (
    <>
      <Button
        variant="contained"
        endIcon={<ArrowDropDownIcon />}
        onClick={(e) => setAnchorEl(e.currentTarget)}
        disabled={statusMutation.isPending}
      >
        Change Status
      </Button>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        {nextStatuses.map((status) => (
          <MenuItem key={status} onClick={() => handleClick(status)}>
            {status.replace(/_/g, ' ')}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}

// ---------------------------------------------------------------------------
// Tab: Overview
// ---------------------------------------------------------------------------

function OverviewTab({
  detail,
  prospectId,
}: {
  detail: ProspectDetailDto;
  prospectId: number;
}) {
  const { prospect, opportunity: opp, scoreBreakdown } = detail;
  const { enqueueSnackbar } = useSnackbar();
  const recalcMutation = useRecalculateScore();

  const oppFacts = useMemo(() => {
    if (!opp) return [];
    return [
      { label: 'Department', value: opp.departmentName ?? '--' },
      { label: 'Office', value: opp.office ?? '--' },
      { label: 'NAICS', value: opp.naicsCode ?? '--' },
      {
        label: 'Set-Aside',
        value:
          [opp.setAsideCode, opp.setAsideDescription]
            .filter(Boolean)
            .join(' - ') || '--',
      },
      { label: 'Posted Date', value: formatDate(opp.postedDate) },
      { label: 'Response Deadline', value: formatDate(opp.responseDeadline) },
      { label: 'Place of Performance', value: buildPoP(opp) },
      {
        label: 'Estimated Value',
        value: formatCurrency(opp.awardAmount) ?? '--',
      },
    ];
  }, [opp]);

  const handleRecalculate = () => {
    recalcMutation.mutate(prospectId, {
      onSuccess: () => {
        enqueueSnackbar('Score recalculated', { variant: 'success' });
      },
      onError: () => {
        enqueueSnackbar('Failed to recalculate score', { variant: 'error' });
      },
    });
  };

  return (
    <Box>
      {/* Linked Opportunity Summary */}
      {opp && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            Linked Opportunity
          </Typography>
          <KeyFactsGrid facts={oppFacts} columns={2} />
          {opp.link && (
            <Box sx={{ mt: 2 }}>
              <Link
                href={opp.link}
                target="_blank"
                rel="noopener noreferrer"
                sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
              >
                View on SAM.gov <OpenInNewIcon fontSize="small" />
              </Link>
            </Box>
          )}
        </Paper>
      )}

      {/* Score Breakdown */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="subtitle2">Score Breakdown</Typography>
          <Button
            size="small"
            variant="outlined"
            onClick={handleRecalculate}
            disabled={recalcMutation.isPending}
          >
            Recalculate Score
          </Button>
        </Box>
        {scoreBreakdown ? (
          <ScoreBreakdownPanel breakdown={scoreBreakdown} />
        ) : (
          <Typography variant="body2" color="text.secondary">
            No score breakdown available. Click Recalculate to generate.
          </Typography>
        )}
      </Paper>

      {/* Win Probability & Financials */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Financials & Outcome
        </Typography>
        <KeyFactsGrid
          facts={[
            {
              label: 'Win Probability',
              value:
                prospect.winProbability != null
                  ? formatPercent(prospect.winProbability)
                  : '--',
            },
            {
              label: 'Estimated Gross Margin',
              value:
                prospect.estimatedGrossMarginPct != null
                  ? formatPercent(prospect.estimatedGrossMarginPct)
                  : '--',
            },
            {
              label: 'Bid Submitted Date',
              value: formatDate(prospect.bidSubmittedDate),
            },
            { label: 'Outcome', value: prospect.outcome ?? '--' },
            {
              label: 'Outcome Notes',
              value: prospect.outcomeNotes ?? '--',
            },
          ]}
          columns={2}
        />
      </Paper>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Score Breakdown Panel
// ---------------------------------------------------------------------------

function ScoreBreakdownPanel({ breakdown }: { breakdown: ScoreBreakdownDto }) {
  const criteria = [
    { label: 'Set-Aside', data: breakdown.breakdown.setAside },
    { label: 'Time Remaining', data: breakdown.breakdown.timeRemaining },
    { label: 'NAICS Match', data: breakdown.breakdown.naicsMatch },
    { label: 'Award Value', data: breakdown.breakdown.awardValue },
  ];

  const pct = breakdown.maxScore > 0 ? (breakdown.totalScore / breakdown.maxScore) * 100 : 0;

  return (
    <Box>
      {criteria.map((c) => {
        const valuePct = c.data.max > 0 ? (c.data.score / c.data.max) * 100 : 0;
        return (
          <Box key={c.label} sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2">{c.label}</Typography>
              <Typography variant="body2" color="text.secondary">
                {c.data.score}/{c.data.max}
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={valuePct}
              sx={{ height: 8, borderRadius: 4 }}
            />
            <Typography variant="caption" color="text.secondary">
              {c.data.detail}
            </Typography>
          </Box>
        );
      })}

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, mt: 3 }}>
        <PWinGauge
          score={pct}
          category={scoreCategory(pct)}
          size="medium"
          showCategory={false}
        />
        <Box>
          <Typography variant="h6" fontWeight={700}>
            {breakdown.totalScore}/{breakdown.maxScore}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Overall Score ({Math.round(pct)}%)
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab: Notes
// ---------------------------------------------------------------------------

function NotesTab({
  detail,
  prospectId,
}: {
  detail: ProspectDetailDto;
  prospectId: number;
}) {
  const [noteText, setNoteText] = useState('');
  const { enqueueSnackbar } = useSnackbar();
  const addNoteMutation = useAddProspectNote();

  const handleAddNote = () => {
    if (!noteText.trim()) return;
    addNoteMutation.mutate(
      { id: prospectId, data: { noteText: noteText.trim() } },
      {
        onSuccess: () => {
          setNoteText('');
          enqueueSnackbar('Note added', { variant: 'success' });
        },
        onError: () => {
          enqueueSnackbar('Failed to add note', { variant: 'error' });
        },
      },
    );
  };

  const sortedNotes = useMemo(
    () =>
      [...detail.notes].sort(
        (a, b) =>
          new Date(b.createdAt ?? 0).getTime() -
          new Date(a.createdAt ?? 0).getTime(),
      ),
    [detail.notes],
  );

  return (
    <Box>
      {/* Add note form */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Add Note
        </Typography>
        <TextField
          fullWidth
          multiline
          minRows={2}
          placeholder="Enter a note..."
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          sx={{ mb: 1 }}
        />
        <Button
          variant="contained"
          size="small"
          onClick={handleAddNote}
          disabled={!noteText.trim() || addNoteMutation.isPending}
        >
          Submit
        </Button>
      </Paper>

      {/* Note feed */}
      {sortedNotes.length === 0 ? (
        <EmptyState
          title="No Notes"
          message="No notes have been added to this prospect yet."
        />
      ) : (
        sortedNotes.map((note) => (
          <Paper
            key={note.noteId}
            variant="outlined"
            sx={{ p: 2, mb: 1.5 }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="subtitle2">
                {note.createdBy?.displayName ?? 'Unknown'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {formatRelative(note.createdAt)}
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {note.noteText}
            </Typography>
          </Paper>
        ))
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab: Team (Teaming Partners)
// ---------------------------------------------------------------------------

function TeamTab({
  detail,
  prospectId,
}: {
  detail: ProspectDetailDto;
  prospectId: number;
}) {
  const { enqueueSnackbar } = useSnackbar();
  const addMemberMutation = useAddTeamMember();
  const removeMemberMutation = useRemoveTeamMember();

  const [uei, setUei] = useState('');
  const [role, setRole] = useState('');
  const [rate, setRate] = useState('');
  const [commitment, setCommitment] = useState('');
  const [notes, setNotes] = useState('');

  const [confirmRemove, setConfirmRemove] = useState<ProspectTeamMemberDto | null>(null);

  const handleAdd = () => {
    addMemberMutation.mutate(
      {
        id: prospectId,
        data: {
          ueiSam: uei || undefined,
          role: role || undefined,
          proposedHourlyRate: rate ? parseFloat(rate) : undefined,
          commitmentPct: commitment ? parseFloat(commitment) : undefined,
          notes: notes || undefined,
        },
      },
      {
        onSuccess: () => {
          setUei('');
          setRole('');
          setRate('');
          setCommitment('');
          setNotes('');
          enqueueSnackbar('Team member added', { variant: 'success' });
        },
        onError: () => {
          enqueueSnackbar('Failed to add team member', { variant: 'error' });
        },
      },
    );
  };

  const handleRemove = () => {
    if (!confirmRemove) return;
    removeMemberMutation.mutate(
      { id: prospectId, memberId: confirmRemove.id },
      {
        onSuccess: () => {
          setConfirmRemove(null);
          enqueueSnackbar('Team member removed', { variant: 'success' });
        },
        onError: () => {
          enqueueSnackbar('Failed to remove team member', { variant: 'error' });
        },
      },
    );
  };

  return (
    <Box>
      {/* Add form */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Add Team Member
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
          <TextField
            size="small"
            label="UEI"
            value={uei}
            onChange={(e) => setUei(e.target.value)}
            sx={{ minWidth: { xs: '100%', sm: 'auto' } }}
          />
          <TextField
            size="small"
            label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            sx={{ minWidth: { xs: '100%', sm: 'auto' } }}
          />
          <TextField
            size="small"
            label="Rate ($/hr)"
            type="number"
            value={rate}
            onChange={(e) => setRate(e.target.value)}
            sx={{ width: { xs: '100%', sm: 120 } }}
          />
          <TextField
            size="small"
            label="Commitment %"
            type="number"
            value={commitment}
            onChange={(e) => setCommitment(e.target.value)}
            sx={{ width: { xs: '100%', sm: 130 } }}
          />
          <TextField
            size="small"
            label="Notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            sx={{ minWidth: { xs: '100%', sm: 'auto' } }}
          />
        </Box>
        <Button
          variant="contained"
          size="small"
          onClick={handleAdd}
          disabled={addMemberMutation.isPending}
        >
          Add
        </Button>
      </Paper>

      {/* Team table */}
      {detail.teamMembers.length === 0 ? (
        <EmptyState
          title="No Team Members"
          message="No teaming partners have been added to this prospect yet."
        />
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ minWidth: 700 }}>
            <TableHead>
              <TableRow>
                <TableCell>Entity Name</TableCell>
                <TableCell>UEI</TableCell>
                <TableCell>Role</TableCell>
                <TableCell align="right">Proposed Rate</TableCell>
                <TableCell align="right">Commitment %</TableCell>
                <TableCell>Notes</TableCell>
                <TableCell width={48} />
              </TableRow>
            </TableHead>
            <TableBody>
              {detail.teamMembers.map((member) => (
                <TableRow key={member.id}>
                  <TableCell>{member.entityName ?? '--'}</TableCell>
                  <TableCell>{member.ueiSam ?? '--'}</TableCell>
                  <TableCell>{member.role ?? '--'}</TableCell>
                  <TableCell align="right">
                    {member.proposedHourlyRate != null
                      ? `$${member.proposedHourlyRate.toFixed(2)}`
                      : '--'}
                  </TableCell>
                  <TableCell align="right">
                    {member.commitmentPct != null
                      ? `${member.commitmentPct}%`
                      : '--'}
                  </TableCell>
                  <TableCell>{member.notes ?? '--'}</TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => setConfirmRemove(member)}
                      aria-label="Remove team member"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <ConfirmDialog
        open={!!confirmRemove}
        title="Remove Team Member"
        message={`Remove ${confirmRemove?.entityName ?? confirmRemove?.ueiSam ?? 'this team member'}?`}
        severity="error"
        confirmText="Remove"
        onConfirm={handleRemove}
        onCancel={() => setConfirmRemove(null)}
        loading={removeMemberMutation.isPending}
      />
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab: Proposal
// ---------------------------------------------------------------------------

function ProposalTab({
  detail,
  prospectId,
}: {
  detail: ProspectDetailDto;
  prospectId: number;
}) {
  const { enqueueSnackbar } = useSnackbar();
  const createProposalMutation = useCreateProposal();
  const proposal = detail.proposal;

  const handleCreate = () => {
    createProposalMutation.mutate(
      { prospectId },
      {
        onSuccess: () => {
          enqueueSnackbar('Proposal created', { variant: 'success' });
        },
        onError: () => {
          enqueueSnackbar('Failed to create proposal', { variant: 'error' });
        },
      },
    );
  };

  if (!proposal) {
    return (
      <EmptyState
        title="No Proposal"
        message="No proposal has been created for this prospect yet."
        action={
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={createProposalMutation.isPending}
          >
            Create Proposal
          </Button>
        }
      />
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 2 }}>
        Proposal Summary
      </Typography>
      <KeyFactsGrid
        facts={[
          { label: 'Status', value: proposal.proposalStatus },
          {
            label: 'Submission Deadline',
            value: formatDate(proposal.submissionDeadline),
          },
          {
            label: 'Submitted At',
            value: formatDate(proposal.submittedAt),
          },
          {
            label: 'Estimated Value',
            value: formatCurrency(proposal.estimatedValue),
          },
        ]}
        columns={2}
      />
      <Box sx={{ mt: 2 }}>
        <Button
          variant="outlined"
          component={RouterLink}
          to={`/prospects/${prospectId}/proposals/${proposal.proposalId}`}
        >
          View Full Proposal
        </Button>
      </Box>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Tab: Intelligence
// ---------------------------------------------------------------------------

function IntelTab({ detail }: { detail: ProspectDetailDto }) {
  const opp = detail.opportunity;

  if (!opp) {
    return (
      <EmptyState
        title="No Opportunity Linked"
        message="No opportunity data is available for intelligence display."
      />
    );
  }

  const facts = [
    { label: 'Title', value: opp.title ?? '--' },
    { label: 'Solicitation Number', value: opp.solicitationNumber ?? '--' },
    { label: 'Department', value: opp.departmentName ?? '--' },
    { label: 'Sub-Tier', value: opp.subTier ?? '--' },
    { label: 'Office', value: opp.office ?? '--' },
    { label: 'Type', value: opp.type ?? '--' },
    { label: 'NAICS', value: opp.naicsCode ?? '--' },
    {
      label: 'Set-Aside',
      value:
        [opp.setAsideCode, opp.setAsideDescription]
          .filter(Boolean)
          .join(' - ') || '--',
    },
    { label: 'Posted Date', value: formatDate(opp.postedDate) },
    { label: 'Response Deadline', value: formatDate(opp.responseDeadline) },
    { label: 'Place of Performance', value: buildPoP(opp) },
    { label: 'Active', value: opp.active ?? '--' },
    {
      label: 'Award Amount',
      value: formatCurrency(opp.awardAmount),
    },
  ];

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 2 }}>
        Opportunity Intelligence
      </Typography>
      <KeyFactsGrid facts={facts} columns={2} />
      {opp.link && (
        <Box sx={{ mt: 2 }}>
          <Link
            href={opp.link}
            target="_blank"
            rel="noopener noreferrer"
            sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
          >
            View on SAM.gov <OpenInNewIcon fontSize="small" />
          </Link>
        </Box>
      )}
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function ProspectDetailPage() {
  const { id: idParam } = useParams<{ id: string }>();
  const prospectId = Number(idParam);

  const {
    data: detail,
    isLoading,
    isError,
    refetch,
  } = useProspect(prospectId, !isNaN(prospectId) && prospectId > 0);

  // --- Loading / Error / Not Found ---
  if (isLoading) {
    return (
      <Box>
        <BackToSearch searchPath="/prospects" />
        <LoadingState message="Loading prospect details..." />
      </Box>
    );
  }

  if (isError) {
    return (
      <Box>
        <BackToSearch searchPath="/prospects" />
        <ErrorState
          title="Failed to load prospect"
          message="An error occurred while loading this prospect. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  if (!detail) {
    return (
      <Box>
        <BackToSearch searchPath="/prospects" />
        <ErrorState
          title="Prospect not found"
          message="The requested prospect could not be found."
        />
      </Box>
    );
  }

  const { prospect, opportunity: opp } = detail;
  const priority = prospect.priority?.toUpperCase() ?? '';

  // --- Tabs ---
  const tabs = [
    {
      label: 'Overview',
      value: 'overview',
      content: <OverviewTab detail={detail} prospectId={prospectId} />,
    },
    {
      label: 'Notes',
      value: 'notes',
      content: <NotesTab detail={detail} prospectId={prospectId} />,
    },
    {
      label: 'Team',
      value: 'team',
      content: <TeamTab detail={detail} prospectId={prospectId} />,
    },
    {
      label: 'Proposal',
      value: 'proposal',
      content: <ProposalTab detail={detail} prospectId={prospectId} />,
    },
    {
      label: 'Intelligence',
      value: 'intelligence',
      content: <IntelTab detail={detail} />,
    },
  ];

  return (
    <TabbedDetailPage tabs={tabs}>
      {/* Back button */}
      <BackToSearch searchPath="/prospects" />

      {/* Header */}
      <PageHeader
        title={opp?.title ?? 'Untitled Prospect'}
        subtitle={opp?.solicitationNumber ?? undefined}
        actions={
          <Box sx={{ display: 'flex', gap: 1 }}>
            <StatusTransitionButton
              prospectId={prospectId}
              currentStatus={prospect.status}
            />
          </Box>
        }
      />

      {/* Summary row */}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 1.5,
          mb: 3,
        }}
      >
        <StatusChip status={prospect.status} />

        {priority && (
          <Chip
            label={priority}
            size="small"
            color={PRIORITY_COLOR[priority] ?? 'default'}
          />
        )}

        <DeadlineCountdown deadline={opp?.responseDeadline ?? null} />

        {detail.scoreBreakdown && (
          <Typography variant="body2" fontWeight={600}>
            Score: {detail.scoreBreakdown.totalScore}/{detail.scoreBreakdown.maxScore}
          </Typography>
        )}

        {prospect.assignedTo && (
          <Chip
            label={`Assigned: ${prospect.assignedTo.displayName}`}
            size="small"
            variant="outlined"
          />
        )}

        {prospect.captureManager && (
          <Chip
            label={`Capture: ${prospect.captureManager.displayName}`}
            size="small"
            variant="outlined"
          />
        )}

        {prospect.estimatedValue != null && (
          <Typography variant="h6" component="span" sx={{ ml: 'auto', fontWeight: 700 }}>
            <CurrencyDisplay value={prospect.estimatedValue} compact />
          </Typography>
        )}
      </Box>
    </TabbedDetailPage>
  );
}
