import {
  Box,
  Typography,
  Paper,
  Button,
  Divider,
  Chip,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  Alert,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import type { WizardFormData } from './CompanySetupWizard';

interface ReviewStepProps {
  data: WizardFormData;
  onGoToStep: (step: number) => void;
  onComplete: () => void;
  isSaving: boolean;
  saveError: string | null;
}

export function ReviewStep({ data, onGoToStep, onComplete, isSaving, saveError }: ReviewStepProps) {
  const formatCurrency = (value: number | null) => {
    if (value == null) return 'N/A';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
  };

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Review & Complete Setup
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Review your information below. Click &quot;Edit&quot; on any section to make changes.
      </Typography>

      {saveError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {saveError}
        </Alert>
      )}

      {/* Company Info */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Company Information
          </Typography>
          <Button size="small" startIcon={<EditIcon />} onClick={() => onGoToStep(0)}>
            Edit
          </Button>
        </Box>
        <Divider sx={{ mb: 1.5 }} />
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1 }}>
          <InfoItem label="Legal Name" value={data.legalName} />
          <InfoItem label="DBA Name" value={data.dbaName} />
          <InfoItem label="UEI" value={data.ueiSam} />
          <InfoItem label="CAGE Code" value={data.cageCode} />
          <InfoItem label="Entity Structure" value={data.entityStructure} />
          <InfoItem
            label="Address"
            value={[
              data.addressLine1,
              data.addressLine2,
              [data.city, data.stateCode, data.zipCode].filter(Boolean).join(', '),
            ]
              .filter(Boolean)
              .join(', ')}
          />
          <InfoItem label="Phone" value={data.phone} />
          <InfoItem label="Website" value={data.website} />
        </Box>
      </Paper>

      {/* NAICS Codes */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            NAICS Codes ({data.naicsCodes.length})
          </Typography>
          <Button size="small" startIcon={<EditIcon />} onClick={() => onGoToStep(1)}>
            Edit
          </Button>
        </Box>
        <Divider sx={{ mb: 1.5 }} />
        {data.naicsCodes.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No NAICS codes added.
          </Typography>
        ) : (
          <List dense disablePadding>
            {data.naicsCodes.map((n) => (
              <ListItem key={n.naicsCode} disableGutters>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2">
                        {n.naicsCode} - {n.naicsTitle}
                      </Typography>
                      {n.isPrimary && <Chip label="Primary" size="small" color="primary" />}
                      {n.sizeStandardMet && (
                        <Chip label="Size Standard Met" size="small" variant="outlined" />
                      )}
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        )}
        {(data.employeeCount || data.annualRevenue) && (
          <Box sx={{ mt: 1, display: 'flex', gap: 3 }}>
            {data.employeeCount && (
              <Typography variant="body2" color="text.secondary">
                Employees: {data.employeeCount.toLocaleString()}
              </Typography>
            )}
            {data.annualRevenue && (
              <Typography variant="body2" color="text.secondary">
                Annual Revenue: {formatCurrency(data.annualRevenue)}
              </Typography>
            )}
          </Box>
        )}
      </Paper>

      {/* Certifications */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Certifications
          </Typography>
          <Button size="small" startIcon={<EditIcon />} onClick={() => onGoToStep(2)}>
            Edit
          </Button>
        </Box>
        <Divider sx={{ mb: 1.5 }} />
        {data.noCertifications ? (
          <Typography variant="body2" color="text.secondary">
            No certifications.
          </Typography>
        ) : data.certifications.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No certifications selected.
          </Typography>
        ) : (
          <List dense disablePadding>
            {data.certifications.map((c) => (
              <ListItem key={c.certificationType} disableGutters>
                <ListItemText
                  primary={c.certificationType}
                  secondary={[
                    c.certificationNumber ? `#${c.certificationNumber}` : null,
                    c.expirationDate ? `Expires: ${c.expirationDate}` : null,
                  ]
                    .filter(Boolean)
                    .join(' | ')}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Paper>

      {/* Past Performance */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Past Performance
          </Typography>
          <Button size="small" startIcon={<EditIcon />} onClick={() => onGoToStep(3)}>
            Edit
          </Button>
        </Box>
        <Divider sx={{ mb: 1.5 }} />
        {data.skipPastPerformance || data.pastPerformances.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {data.skipPastPerformance ? 'Skipped.' : 'No contracts added.'}
          </Typography>
        ) : (
          <List dense disablePadding>
            {data.pastPerformances.map((pp, i) => (
              <ListItem key={i} disableGutters>
                <ListItemText
                  primary={`${pp.contractNumber || 'Contract'} - ${pp.agencyName || 'Unknown Agency'}`}
                  secondary={[
                    pp.naicsCode ? `NAICS: ${pp.naicsCode}` : null,
                    pp.contractValue ? `Value: ${formatCurrency(pp.contractValue)}` : null,
                  ]
                    .filter(Boolean)
                    .join(' | ')}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Paper>

      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <Button
          variant="contained"
          size="large"
          onClick={onComplete}
          disabled={isSaving}
          startIcon={isSaving ? <CircularProgress size={20} /> : undefined}
          sx={{ minWidth: 200 }}
        >
          {isSaving ? 'Saving...' : 'Complete Setup'}
        </Button>
      </Box>
    </Box>
  );
}

function InfoItem({ label, value }: { label: string; value: string | undefined | null }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2">{value || '-'}</Typography>
    </Box>
  );
}
