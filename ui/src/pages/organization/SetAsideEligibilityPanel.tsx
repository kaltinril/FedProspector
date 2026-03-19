import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';

import { useOrgCertifications } from '@/queries/useOrganization';
import type { OrgCertificationDto, OrganizationEntityDto } from '@/types/organization';
import { getSetAsideChipProps } from '@/utils/constants';

interface SetAsideEligibilityPanelProps {
  linkedEntities: OrganizationEntityDto[];
  isLoadingEntities: boolean;
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
}

function CertChip({ cert }: { cert: OrgCertificationDto }) {
  const chipProps = getSetAsideChipProps(cert.certificationType);
  const expLabel = cert.expirationDate
    ? ` (expires ${formatDate(cert.expirationDate)})`
    : '';

  return (
    <Chip
      label={`${cert.certificationType}${expLabel}`}
      size="small"
      color={chipProps.color}
      sx={{ ...chipProps.sx, mr: 1, mb: 1 }}
    />
  );
}

function CertSection({
  title,
  subtitle,
  certs,
}: {
  title: string;
  subtitle: string;
  certs: OrgCertificationDto[];
}) {
  if (certs.length === 0) return null;

  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="subtitle2" gutterBottom>
        {title}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
        {subtitle}
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap' }}>
        {certs.map((cert) => (
          <CertChip key={`${cert.certificationType}-${cert.source}`} cert={cert} />
        ))}
      </Box>
    </Box>
  );
}

export function SetAsideEligibilityPanel({
  linkedEntities,
  isLoadingEntities,
}: SetAsideEligibilityPanelProps) {
  const { data: certifications = [], isLoading: isLoadingCerts } = useOrgCertifications();

  const hasSelf = linkedEntities.some((e) => e.relationship === 'SELF' && e.isActive);

  const samCerts = certifications.filter((c) => c.source === 'SAM_ENTITY' && c.isActive);
  const manualCerts = certifications.filter(
    (c) => (!c.source || c.source === 'MANUAL') && c.isActive,
  );

  const isLoading = isLoadingEntities || isLoadingCerts;

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
      ) : samCerts.length === 0 && manualCerts.length === 0 ? (
        <Alert severity="info" sx={{ mt: 1 }}>
          No certifications found. Your SAM.gov entity has no set-aside certifications on record.
        </Alert>
      ) : (
        <Box>
          <CertSection
            title="From Linked Entities"
            subtitle="Synced from SAM.gov entity registrations. These are managed by your SAM.gov registration."
            certs={samCerts}
          />

          {samCerts.length > 0 && manualCerts.length > 0 && <Divider sx={{ my: 1.5 }} />}

          <CertSection
            title="Manually Declared"
            subtitle="Added during company setup. These can be updated via the setup wizard."
            certs={manualCerts}
          />
        </Box>
      )}
    </Paper>
  );
}
