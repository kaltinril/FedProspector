import {
  Box,
  Typography,
  Checkbox,
  FormControlLabel,
  TextField,
  Collapse,
  Paper,
  Button,
} from '@mui/material';
import { CERTIFICATION_TYPES } from '@/utils/constants';

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

export function CertificationsStep({
  certifications,
  noCertifications,
  onChange,
  onNext,
  onBack,
}: CertificationsStepProps) {
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
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Select the certifications your company holds. These help match you to set-aside
        opportunities.
      </Typography>

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
                label={<Typography fontWeight={checked ? 600 : 400}>{type}</Typography>}
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

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" size="large" onClick={onNext}>
          Next
        </Button>
      </Box>
    </Box>
  );
}
