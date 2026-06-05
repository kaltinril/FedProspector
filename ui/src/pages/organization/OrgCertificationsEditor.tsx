import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSnackbar } from 'notistack';
import { useSetOrgCertifications } from '@/queries/useOrganization';
import { CERTIFICATION_TYPES } from '@/utils/constants';
import { formatDate } from '@/utils/dateFormatters';
import type { OrgCertificationDto } from '@/types/organization';

/**
 * Phase 136 Unit A: add/remove organization certifications. Only MANUAL-source certs are
 * editable here; SAM_ENTITY-synced certs render read-only (Phase 101 semantics — the
 * PUT /org/certifications endpoint only replaces MANUAL rows). Read-only when canEdit=false.
 */
interface OrgCertificationsEditorProps {
  certifications: OrgCertificationDto[];
  canEdit: boolean;
}

export function OrgCertificationsEditor({ certifications, canEdit }: OrgCertificationsEditorProps) {
  const { enqueueSnackbar } = useSnackbar();
  const setCertsMutation = useSetOrgCertifications();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<OrgCertificationDto[]>([]);
  const [error, setError] = useState('');
  // New-cert form state.
  const [newType, setNewType] = useState('');
  const [newNumber, setNewNumber] = useState('');
  const [newExpiration, setNewExpiration] = useState('');

  const manualCerts = certifications.filter((c) => c.source === 'MANUAL');
  const syncedCerts = certifications.filter((c) => c.source !== 'MANUAL');

  const handleStart = () => {
    setDraft(manualCerts.map((c) => ({ ...c })));
    setError('');
    setNewType('');
    setNewNumber('');
    setNewExpiration('');
    setEditing(true);
  };

  const handleCancel = () => {
    setEditing(false);
    setError('');
  };

  const handleAddRow = () => {
    if (!newType) {
      setError('Select a certification type to add.');
      return;
    }
    if (draft.some((c) => c.certificationType === newType)) {
      setError('That certification type is already in the list.');
      return;
    }
    setDraft([
      ...draft,
      {
        certificationType: newType,
        certificationNumber: newNumber.trim() || null,
        expirationDate: newExpiration || null,
        isActive: true,
        source: 'MANUAL',
      },
    ]);
    setNewType('');
    setNewNumber('');
    setNewExpiration('');
    setError('');
  };

  const handleRemoveRow = (type: string) => {
    setDraft(draft.filter((c) => c.certificationType !== type));
  };

  const handleSave = () => {
    setCertsMutation.mutate(draft, {
      onSuccess: () => {
        setEditing(false);
        setError('');
        enqueueSnackbar('Certifications updated', { variant: 'success' });
      },
      onError: (err) => {
        setError(err instanceof Error ? err.message : 'Failed to save certifications');
      },
    });
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Certifications
        </Typography>
        {canEdit && !editing && (
          <Button variant="outlined" size="small" onClick={handleStart}>
            Edit
          </Button>
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {syncedCerts.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
            Synced from SAM.gov (read-only):
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {syncedCerts.map((cert) => (
              <Chip
                key={`${cert.certificationType}-${cert.source}`}
                label={
                  cert.expirationDate
                    ? `${cert.certificationType} (expires ${formatDate(cert.expirationDate)})`
                    : cert.certificationType
                }
                size="small"
              />
            ))}
          </Box>
        </Box>
      )}

      {!editing ? (
        manualCerts.length === 0 ? (
          <Alert severity="info">No manually-added certifications.</Alert>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Type</TableCell>
                  <TableCell>Number</TableCell>
                  <TableCell>Expiration</TableCell>
                  <TableCell>Active</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {manualCerts.map((cert) => (
                  <TableRow key={cert.id ?? cert.certificationType}>
                    <TableCell>{cert.certificationType}</TableCell>
                    <TableCell>{cert.certificationNumber || '-'}</TableCell>
                    <TableCell>
                      {cert.expirationDate ? formatDate(cert.expirationDate) : '-'}
                    </TableCell>
                    <TableCell>{cert.isActive ? 'Yes' : 'No'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )
      ) : (
        <>
          <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Type</TableCell>
                  <TableCell>Number</TableCell>
                  <TableCell>Expiration</TableCell>
                  <TableCell>Active</TableCell>
                  <TableCell align="center" width={60} />
                </TableRow>
              </TableHead>
              <TableBody>
                {draft.map((cert) => (
                  <TableRow key={cert.certificationType}>
                    <TableCell>{cert.certificationType}</TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        value={cert.certificationNumber ?? ''}
                        onChange={(e) =>
                          setDraft(
                            draft.map((c) =>
                              c.certificationType === cert.certificationType
                                ? { ...c, certificationNumber: e.target.value || null }
                                : c,
                            ),
                          )
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        type="date"
                        value={cert.expirationDate ?? ''}
                        onChange={(e) =>
                          setDraft(
                            draft.map((c) =>
                              c.certificationType === cert.certificationType
                                ? { ...c, expirationDate: e.target.value || null }
                                : c,
                            ),
                          )
                        }
                        slotProps={{ inputLabel: { shrink: true } }}
                      />
                    </TableCell>
                    <TableCell>
                      <FormControlLabel
                        control={
                          <Switch
                            size="small"
                            checked={cert.isActive}
                            onChange={(e) =>
                              setDraft(
                                draft.map((c) =>
                                  c.certificationType === cert.certificationType
                                    ? { ...c, isActive: e.target.checked }
                                    : c,
                                ),
                              )
                            }
                          />
                        }
                        label=""
                      />
                    </TableCell>
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleRemoveRow(cert.certificationType)}
                        aria-label={`Remove certification ${cert.certificationType}`}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <TextField
              select
              size="small"
              label="Certification Type"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              sx={{ minWidth: 180 }}
            >
              {CERTIFICATION_TYPES.filter(
                (t) => !draft.some((c) => c.certificationType === t),
              ).map((t) => (
                <MenuItem key={t} value={t}>
                  {t}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label="Number"
              value={newNumber}
              onChange={(e) => setNewNumber(e.target.value)}
            />
            <TextField
              size="small"
              type="date"
              label="Expiration"
              value={newExpiration}
              onChange={(e) => setNewExpiration(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <Button variant="outlined" onClick={handleAddRow} disabled={!newType} sx={{ flexShrink: 0 }}>
              Add
            </Button>
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button variant="contained" onClick={handleSave} disabled={setCertsMutation.isPending}>
              Save
            </Button>
            <Button variant="outlined" onClick={handleCancel} disabled={setCertsMutation.isPending}>
              Cancel
            </Button>
          </Box>
        </>
      )}
    </Box>
  );
}
