import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import IconButton from '@mui/material/IconButton';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Select from '@mui/material/Select';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import LinkIcon from '@mui/icons-material/Link';
import SearchIcon from '@mui/icons-material/Search';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  getLinkedEntities,
  linkEntity,
  deactivateEntityLink,
  refreshSelfEntity,
} from '@/api/organization';
import { searchEntities } from '@/api/entities';
import { queryKeys } from '@/queries/queryKeys';
import type { OrganizationEntityDto } from '@/types/organization';
import type { EntitySearchResult } from '@/types/api';

const RELATIONSHIP_OPTIONS = [
  { value: 'SELF', label: 'Self (Your Organization)' },
  { value: 'JV_PARTNER', label: 'JV Partner' },
  { value: 'TEAMING', label: 'Teaming Partner' },
];

export function OrgEntitiesTab() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<EntitySearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<EntitySearchResult | null>(null);
  const [relationship, setRelationship] = useState('SELF');
  const [notes, setNotes] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [searchError, setSearchError] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const { data: linkedEntities = [], isLoading, isError, error } = useQuery({
    queryKey: queryKeys.organization.entities,
    queryFn: getLinkedEntities,
  });

  const linkMutation = useMutation({
    mutationFn: linkEntity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.organization.entities });
      queryClient.invalidateQueries({ queryKey: queryKeys.organization.profile });
      setMutationError(null);
      setLinkDialogOpen(false);
      setSelectedEntity(null);
      setNotes('');
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: deactivateEntityLink,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.organization.entities });
      setMutationError(null);
    },
    onError: (err: Error) => {
      setMutationError(err.message || 'Failed to unlink entity');
    },
  });

  const refreshMutation = useMutation({
    mutationFn: refreshSelfEntity,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.organization.entities });
      queryClient.invalidateQueries({ queryKey: queryKeys.organization.profile });
      queryClient.invalidateQueries({ queryKey: queryKeys.organization.naics });
      queryClient.invalidateQueries({ queryKey: queryKeys.organization.certifications });
      setMutationError(null);
      setSuccessMessage(data.message);
      setTimeout(() => setSuccessMessage(''), 5000);
    },
    onError: (err: Error) => {
      setMutationError(err.message || 'Failed to refresh entity data');
    },
  });

  const handleSearch = async () => {
    const trimmed = searchQuery.trim();
    if (!trimmed) return;
    setSearching(true);
    setSearchError(null);
    try {
      const isUei = /^[A-Z0-9]{12}$/i.test(trimmed);
      const result = await searchEntities({
        name: isUei ? undefined : trimmed,
        uei: isUei ? trimmed : undefined,
        pageSize: 10,
      });
      setSearchResults(result.items);
    } catch (err: unknown) {
      setSearchResults([]);
      const axiosErr = err as { response?: { data?: { error?: string; message?: string } } };
      setSearchError(
        axiosErr.response?.data?.error ?? axiosErr.response?.data?.message ?? 'Search failed',
      );
    }
    setSearching(false);
  };

  const handleSelectEntity = (entity: EntitySearchResult) => {
    setSelectedEntity(entity);
    setLinkDialogOpen(true);
  };

  const handleConfirmLink = () => {
    if (!selectedEntity) return;
    linkMutation.mutate({
      ueiSam: selectedEntity.ueiSam,
      relationship,
      notes: notes || undefined,
    });
  };

  const hasSelf = linkedEntities.some(
    (e: OrganizationEntityDto) => e.relationship === 'SELF',
  );

  const relationshipColor = (rel: string) => {
    switch (rel) {
      case 'SELF':
        return 'primary';
      case 'JV_PARTNER':
        return 'secondary';
      case 'TEAMING':
        return 'info';
      default:
        return 'default';
    }
  };

  return (
    <Box>
      {successMessage && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMessage('')}>
          {successMessage}
        </Alert>
      )}

      {linkMutation.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {(linkMutation.error as Error)?.message || 'Failed to link entity'}
        </Alert>
      )}

      {mutationError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setMutationError(null)}>
          {mutationError}
        </Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">Linked Entities</Typography>
        {hasSelf && (
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
          >
            {refreshMutation.isPending ? 'Refreshing...' : 'Refresh from SAM.gov'}
          </Button>
        )}
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Link your SAM.gov entity (SELF) and teaming/JV partners to auto-populate NAICS codes,
        certifications, and improve pWin scoring accuracy.
      </Typography>

      {/* Search section */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Search SAM.gov Entities
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            size="small"
            placeholder="Search by name or UEI..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            sx={{ flex: 1 }}
          />
          <Button
            variant="contained"
            startIcon={searching ? <CircularProgress size={16} /> : <SearchIcon />}
            onClick={handleSearch}
            disabled={searching || !searchQuery.trim()}
          >
            Search
          </Button>
        </Box>

        {searchError && (
          <Alert severity="error" sx={{ mt: 1 }} onClose={() => setSearchError(null)}>
            {searchError}
          </Alert>
        )}

        {searchResults.length > 0 && (
          <TableContainer sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Entity Name</TableCell>
                  <TableCell>UEI</TableCell>
                  <TableCell>Primary NAICS</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {searchResults.map((entity) => (
                  <TableRow key={entity.ueiSam} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>
                        {entity.legalBusinessName}
                      </Typography>
                      {entity.dbaName && (
                        <Typography variant="caption" color="text.secondary">
                          DBA: {entity.dbaName}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontFamily="monospace">
                        {entity.ueiSam}
                      </Typography>
                    </TableCell>
                    <TableCell>{entity.primaryNaics || '-'}</TableCell>
                    <TableCell>
                      <Chip
                        label={entity.registrationStatus === 'A' ? 'Active' : entity.registrationStatus || 'Unknown'}
                        size="small"
                        color={entity.registrationStatus === 'A' ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        size="small"
                        startIcon={<LinkIcon />}
                        onClick={() => handleSelectEntity(entity)}
                        disabled={linkedEntities.some(
                          (l: OrganizationEntityDto) => l.ueiSam === entity.ueiSam && l.isActive,
                        )}
                      >
                        Link
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Linked entities table */}
      {isLoading ? (
        <CircularProgress />
      ) : isError ? (
        <Alert severity="error">
          Failed to load linked entities: {(error as Error)?.message || 'Unknown error'}
        </Alert>
      ) : linkedEntities.length === 0 ? (
        <Alert severity="info">
          No entities linked yet. Search above to link your SAM.gov entity.
        </Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Entity</TableCell>
                <TableCell>UEI</TableCell>
                <TableCell>Relationship</TableCell>
                <TableCell align="center">NAICS</TableCell>
                <TableCell align="center">Certs</TableCell>
                <TableCell>Added By</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {linkedEntities.map((link: OrganizationEntityDto) => (
                <TableRow key={link.id}>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {link.legalBusinessName || link.ueiSam}
                    </Typography>
                    {link.cageCode && (
                      <Typography variant="caption" color="text.secondary">
                        CAGE: {link.cageCode}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {link.ueiSam}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={link.relationship}
                      size="small"
                      color={relationshipColor(link.relationship) as 'primary' | 'secondary' | 'info' | 'default'}
                    />
                  </TableCell>
                  <TableCell align="center">{link.naicsCount}</TableCell>
                  <TableCell align="center">{link.certificationCount}</TableCell>
                  <TableCell>{link.addedByName || '-'}</TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => deactivateMutation.mutate(link.id)}
                      disabled={deactivateMutation.isPending}
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

      {/* Link confirmation dialog */}
      <Dialog open={linkDialogOpen} onClose={() => setLinkDialogOpen(false)} disableRestoreFocus maxWidth="sm" fullWidth>
        <DialogTitle>Link Entity</DialogTitle>
        <DialogContent>
          {selectedEntity && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={500}>
                {selectedEntity.legalBusinessName}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                UEI: {selectedEntity.ueiSam}
                {selectedEntity.primaryNaics && ` | Primary NAICS: ${selectedEntity.primaryNaics}`}
              </Typography>
            </Box>
          )}
          <FormControl fullWidth sx={{ mb: 2, mt: 1 }}>
            <InputLabel>Relationship</InputLabel>
            <Select
              value={relationship}
              label="Relationship"
              onChange={(e) => setRelationship(e.target.value)}
            >
              {RELATIONSHIP_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            fullWidth
            multiline
            rows={2}
            label="Notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          {relationship === 'SELF' && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Linking as SELF will copy NAICS codes, certifications, and profile fields from this
              entity to your organization.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLinkDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleConfirmLink}
            disabled={linkMutation.isPending}
          >
            {linkMutation.isPending ? 'Linking...' : 'Confirm Link'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
