import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  FormControlLabel,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import { useOrgCertifications, useOrgEntities } from '@/queries/useOrganization';
import { CERTIFICATION_TYPES, getSetAsideChipProps } from '@/utils/constants';
import type { OrgCertificationDto } from '@/types/organization';

export interface CertificationEntry {
  certificationType: string;
  certificationNumber: string;
  expirationDate: string | null;
}

interface CertificationsStepProps {
  certifications: CertificationEntry[];
  noCertifications: boolean;
  onChange: (certifications: CertificationEntry[], noCertifications: boolean) => void;
  onNext: () => void;
  onBack: () => void;
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
}

function ReadOnlyCertView({ certs }: { certs: OrgCertificationDto[] }) {
  const activeCerts = certs.filter((c) => c.isActive);

  return (
    <Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        Certifications are managed by your SAM.gov entity registration. To update them, modify
        your SAM.gov registration and refresh from the Organization &rarr; Entity Linking tab.
      </Alert>
      {activeCerts.length === 0 ? (
        <Typography variant="body2" sx={{
          color: "text.secondary"
        }}>
          No certifications found on your linked SAM.gov entity.
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {activeCerts.map((cert) => {
            const chipProps = getSetAsideChipProps(cert.certificationType);
            const expLabel = cert.expirationDate
              ? ` (expires ${formatDate(cert.expirationDate)})`
              : '';
            return (
              <Chip
                key={`${cert.certificationType}-${cert.source}`}
                label={`${cert.certificationType}${expLabel}`}
                color={chipProps.color}
                sx={chipProps.sx}
              />
            );
          })}
        </Box>
      )}
    </Box>
  );
}

export function CertificationsStep({
  certifications,
  noCertifications,
  onChange,
  onNext,
  onBack,
}: CertificationsStepProps) {
  const { data: linkedEntities = [], isLoading: isLoadingEntities } = useOrgEntities();
  const { data: orgCerts = [], isLoading: isLoadingCerts } = useOrgCertifications();

  const hasSelfEntity = linkedEntities.some((e) => e.relationship === 'SELF' && e.isActive);
  const isLoading = isLoadingEntities || isLoadingCerts;

  const isChecked = (type: string) => certifications.some((c) => c.certificationType === type);

  const handleToggle = (type: string) => {
    if (noCertifications) return;
    if (isChecked(type)) {
      onChange(
        certifications.filter((c) => c.certificationType !== type),
        false,
      );
    } else {
      onChange(
        [
          ...certifications,
          { certificationType: type, certificationNumber: '', expirationDate: null },
        ],
        false,
      );
    }
  };

  const handleFieldChange = (
    type: string,
    field: 'certificationNumber' | 'expirationDate',
    value: string,
  ) => {
    onChange(
      certifications.map((c) =>
        c.certificationType === type ? { ...c, [field]: value || null } : c,
      ),
      noCertifications,
    );
  };

  const handleNoCertifications = () => {
    const next = !noCertifications;
    onChange(next ? [] : certifications, next);
  };

  const getCert = (type: string) => certifications.find((c) => c.certificationType === type);

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 1 }}>
        Certifications
      </Typography>
      <Typography
        variant="body2"
        sx={{
          color: "text.secondary",
          mb: 3
        }}>
        {hasSelfEntity
          ? 'Your certifications have been synced from your linked SAM.gov entity.'
          : 'Select the certifications your company holds. These help match you to set-aside opportunities.'}
      </Typography>
      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress size={24} />
        </Box>
      ) : hasSelfEntity ? (
        <ReadOnlyCertView certs={orgCerts} />
      ) : (
        <>
          <FormControlLabel
            control={
              <Checkbox checked={noCertifications} onChange={handleNoCertifications} />
            }
            label="We don't have any certifications"
            sx={{ mb: 2 }}
          />

          <Box sx={{ opacity: noCertifications ? 0.5 : 1, pointerEvents: noCertifications ? 'none' : 'auto' }}>
            {CERTIFICATION_TYPES.map((type) => {
              const checked = isChecked(type);
              const cert = getCert(type);
              return (
                <Paper key={type} variant="outlined" sx={{ mb: 1.5, p: 2 }}>
                  <FormControlLabel
                    control={
                      <Checkbox checked={checked} onChange={() => handleToggle(type)} />
                    }
                    label={<Typography sx={{
                      fontWeight: checked ? 600 : 400
                    }}>{type}</Typography>}
                  />
                  <Collapse in={checked}>
                    <Box sx={{ display: 'flex', gap: 2, mt: 1.5, ml: 4 }}>
                      <TextField
                        label="Certification Number"
                        size="small"
                        value={cert?.certificationNumber ?? ''}
                        onChange={(e) =>
                          handleFieldChange(type, 'certificationNumber', e.target.value)
                        }
                        sx={{ flex: 1 }}
                      />
                      <TextField
                        label="Expiration Date"
                        type="date"
                        size="small"
                        value={cert?.expirationDate ?? ''}
                        onChange={(e) =>
                          handleFieldChange(type, 'expirationDate', e.target.value)
                        }
                        slotProps={{ inputLabel: { shrink: true } }}
                        sx={{ width: 200 }}
                      />
                    </Box>
                  </Collapse>
                </Paper>
              );
            })}
          </Box>
        </>
      )}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" size="large" onClick={onNext}>
          Next
        </Button>
      </Box>
    </Box>
  );
}
