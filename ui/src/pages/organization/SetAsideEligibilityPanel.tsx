import { useState } from 'react';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import Divider from '@mui/material/Divider';
import FormControl from '@mui/material/FormControl';
import IconButton from '@mui/material/IconButton';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Select from '@mui/material/Select';
import Typography from '@mui/material/Typography';

import { useOrgCertifications, useSetOrgCertifications } from '@/queries/useOrganization';
import type { OrgCertificationDto, OrganizationEntityDto } from '@/types/organization';
import { getSetAsideChipProps } from '@/utils/constants';

// ---------------------------------------------------------------------------
// Cert-to-set-aside mapping
// ---------------------------------------------------------------------------

interface SetAsideCode {
  code: string;
  label: string;
}

interface SetAsideCategory {
  category: string;
  codes: SetAsideCode[];
}

const CERT_TO_SET_ASIDES: Record<string, SetAsideCategory> = {
  WOSB: {
    category: 'Women-Owned Small Business',
    codes: [
      { code: 'WOSB', label: 'WOSB' },
      { code: 'WOSBSS', label: 'WOSB Sole Source' },
    ],
  },
  EDWOSB: {
    category: 'Economically Disadvantaged WOSB',
    codes: [
      { code: 'EDWOSB', label: 'EDWOSB' },
      { code: 'EDWOSBSS', label: 'EDWOSB Sole Source' },
    ],
  },
  '8(a)': {
    category: '8(a) Program',
    codes: [
      { code: '8A', label: '8(a)' },
      { code: '8AN', label: '8(a) Sole Source' },
    ],
  },
  HUBZone: {
    category: 'HUBZone',
    codes: [
      { code: 'HZC', label: 'HUBZone' },
      { code: 'HZS', label: 'HUBZone Sole Source' },
    ],
  },
  SDVOSB: {
    category: 'Service-Disabled Veteran-Owned',
    codes: [
      { code: 'SDVOSBC', label: 'SDVOSB' },
      { code: 'SDVOSBS', label: 'SDVOSB Sole Source' },
    ],
  },
  VOSB: {
    category: 'Veteran-Owned',
    codes: [
      { code: 'VSA', label: 'Veteran SB Set-Aside' },
      { code: 'VSB', label: 'Veteran SB Sole Source' },
    ],
  },
  SDB: {
    category: 'Small Business',
    codes: [
      { code: 'SBA', label: 'Total Small Business' },
      { code: 'SBP', label: 'SB Set-Aside' },
    ],
  },
};

/** All cert types that can be manually added */
const MANUAL_CERT_TYPES = Object.keys(CERT_TO_SET_ASIDES);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
}

/** Normalize cert type strings for comparison (e.g. 'Small Business' -> 'SDB') */
function normalizeCertType(certType: string): string {
  const upper = certType.toUpperCase();
  if (upper === 'SMALL BUSINESS' || upper === 'SDB') return 'SDB';
  if (upper === 'VETERAN-OWNED' || upper === 'VOSB') return 'VOSB';
  // Return original for types that match mapping keys directly
  return certType;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface SetAsideEligibilityPanelProps {
  linkedEntities: OrganizationEntityDto[];
  isLoadingEntities: boolean;
}

export function SetAsideEligibilityPanel({
  linkedEntities,
  isLoadingEntities,
}: SetAsideEligibilityPanelProps) {
  const { data: certifications = [], isLoading: isLoadingCerts } = useOrgCertifications();
  const setCertsMutation = useSetOrgCertifications();

  const [addOpen, setAddOpen] = useState(false);
  const [selectedType, setSelectedType] = useState('');

  const hasSelf = linkedEntities.some((e) => e.relationship === 'SELF' && e.isActive);
  const isLoading = isLoadingEntities || isLoadingCerts;

  const activeCerts = certifications.filter((c) => c.isActive);
  const samCerts = activeCerts.filter((c) => c.source === 'SAM_ENTITY');
  const manualCerts = activeCerts.filter((c) => !c.source || c.source === 'MANUAL');

  // Build the set of normalized cert types the user holds
  const heldCertTypes = new Set(activeCerts.map((c) => normalizeCertType(c.certificationType)));

  // Build set-aside rows: one per matching CERT_TO_SET_ASIDES entry
  const setAsideRows: { certType: string; category: SetAsideCategory }[] = [];
  for (const [certKey, category] of Object.entries(CERT_TO_SET_ASIDES)) {
    if (heldCertTypes.has(certKey)) {
      setAsideRows.push({ certType: certKey, category });
    }
  }

  // Cert types already present from SAM_ENTITY (cannot be manually added)
  const samCertTypesNormalized = new Set(samCerts.map((c) => normalizeCertType(c.certificationType)));
  // All existing cert types (to filter the add dropdown)
  const allCertTypesNormalized = new Set(activeCerts.map((c) => normalizeCertType(c.certificationType)));

  // Types available to add manually: not already present at all
  const addableCertTypes = MANUAL_CERT_TYPES.filter((t) => !allCertTypesNormalized.has(t));

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function handleAddCert() {
    if (!selectedType) return;
    const currentManual = certifications.filter(
      (c) => (!c.source || c.source === 'MANUAL') && c.isActive,
    );
    const newCert: OrgCertificationDto = {
      certificationType: selectedType,
      isActive: true,
      source: 'MANUAL',
    };
    setCertsMutation.mutate([...currentManual, newCert], {
      onSuccess: () => {
        setSelectedType('');
        setAddOpen(false);
      },
    });
  }

  function handleRemoveManualCert(certType: string) {
    const remaining = certifications.filter(
      (c) =>
        (!c.source || c.source === 'MANUAL') &&
        c.isActive &&
        normalizeCertType(c.certificationType) !== certType,
    );
    setCertsMutation.mutate(remaining);
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        Set-Aside Eligibility
      </Typography>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
          <CircularProgress size={24} />
        </Box>
      ) : !hasSelf && manualCerts.length === 0 ? (
        <Alert severity="info" sx={{ mt: 1 }}>
          Link your SAM.gov entity to see your set-aside eligibility. You can search and link
          entities below.
        </Alert>
      ) : activeCerts.length === 0 ? (
        <Alert severity="info" sx={{ mt: 1 }}>
          No certifications found. Your SAM.gov entity has no set-aside certifications on record.
        </Alert>
      ) : (
        <Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Synced from SAM.gov entity registrations.
          </Typography>

          {setAsideRows.length > 0 && (
            <>
              <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
                You can bid on:
              </Typography>

              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: '200px 1fr' },
                  rowGap: 1.5,
                  columnGap: 2,
                  mb: 2,
                }}
              >
                {setAsideRows.map(({ certType, category }) => (
                  <Box key={certType} sx={{ display: 'contents' }}>
                    <Typography
                      variant="body2"
                      sx={{ alignSelf: 'center', color: 'text.secondary' }}
                    >
                      {category.category}
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
                      {category.codes.map((sa) => {
                        const chipProps = getSetAsideChipProps(sa.code);
                        return (
                          <Chip
                            key={sa.code}
                            label={sa.code}
                            size="small"
                            color={chipProps.color}
                            sx={{ ...chipProps.sx, fontWeight: 500 }}
                            title={sa.label}
                          />
                        );
                      })}
                    </Box>
                  </Box>
                ))}
              </Box>
            </>
          )}

          {/* Based on: cert list */}
          <Divider sx={{ my: 1.5 }} />

          <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
            Based on:{' '}
            {activeCerts.map((cert, idx) => {
              const normalized = normalizeCertType(cert.certificationType);
              const isSam = cert.source === 'SAM_ENTITY';
              const isManual = !cert.source || cert.source === 'MANUAL';
              const canRemove = isManual && !samCertTypesNormalized.has(normalized);
              const expStr = cert.expirationDate
                ? ` exp. ${formatDate(cert.expirationDate)}`
                : '';
              const sourceTag = isSam ? ' (from SAM.gov)' : ' (manually added)';

              return (
                <Box
                  key={`${cert.certificationType}-${cert.source}`}
                  component="span"
                  sx={{ display: 'inline-flex', alignItems: 'center', mr: 0.5 }}
                >
                  {idx > 0 && <Box component="span" sx={{ mr: 0.5 }}>, </Box>}
                  <Box component="span" sx={{ fontWeight: 500 }}>
                    {cert.certificationType}
                  </Box>
                  <Box component="span" sx={{ opacity: 0.7 }}>
                    {expStr}
                    {sourceTag}
                  </Box>
                  {canRemove && (
                    <IconButton
                      size="small"
                      onClick={() => handleRemoveManualCert(normalized)}
                      disabled={setCertsMutation.isPending}
                      sx={{ ml: 0.25, p: 0.25 }}
                      aria-label={`Remove ${cert.certificationType}`}
                    >
                      <CloseIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  )}
                </Box>
              );
            })}
          </Typography>
        </Box>
      )}

      {/* Add certification section */}
      {!isLoading && (
        <Box sx={{ mt: 2 }}>
          {!addOpen ? (
            <Button
              size="small"
              startIcon={<AddIcon />}
              onClick={() => setAddOpen(true)}
              disabled={addableCertTypes.length === 0}
            >
              {addableCertTypes.length === 0
                ? 'All certification types added'
                : 'Add certification manually'}
            </Button>
          ) : (
            <Collapse in={addOpen}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <FormControl size="small" sx={{ minWidth: 180 }}>
                  <InputLabel>Certification type</InputLabel>
                  <Select
                    value={selectedType}
                    label="Certification type"
                    onChange={(e) => setSelectedType(e.target.value)}
                  >
                    {addableCertTypes.map((t) => (
                      <MenuItem key={t} value={t}>
                        {t}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleAddCert}
                  disabled={!selectedType || setCertsMutation.isPending}
                >
                  {setCertsMutation.isPending ? 'Adding...' : 'Add'}
                </Button>
                <Button size="small" onClick={() => { setAddOpen(false); setSelectedType(''); }}>
                  Cancel
                </Button>
              </Box>
              {setCertsMutation.isError && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  {(setCertsMutation.error as Error)?.message || 'Failed to add certification'}
                </Alert>
              )}
            </Collapse>
          )}
        </Box>
      )}
    </Paper>
  );
}
