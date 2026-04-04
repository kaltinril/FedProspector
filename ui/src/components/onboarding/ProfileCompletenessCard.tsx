import { useState } from 'react';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import RadioButtonUncheckedOutlined from '@mui/icons-material/RadioButtonUncheckedOutlined';
import UploadOutlined from '@mui/icons-material/UploadOutlined';
import Alert from '@mui/material/Alert';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { useProfileCompleteness } from '@/queries/useOnboarding';
import { UeiImportDialog } from './UeiImportDialog';

const FIELD_RECOMMENDATIONS: Record<string, string> = {
  'UEI': 'Add your Unique Entity ID to enable SAM.gov data import',
  'CAGE Code': 'Add CAGE code for DoD opportunity matching',
  'NAICS Codes': 'Add NAICS codes to improve opportunity matching',
  'PSC Codes': 'Add PSC codes to match product/service categories',
  'Certifications': 'Add certifications (WOSB, 8a, HUBZone) to find set-aside opportunities',
  'Past Performance': 'Add past performance records to strengthen bid evaluations',
  'Address': 'Add your business address for geographic matching',
  'Business Type': 'Specify your business type for set-aside eligibility',
  'Size Standard': 'Add size standard info to track SBA thresholds',
};

function getRecommendation(field: string): string {
  return FIELD_RECOMMENDATIONS[field] ?? `Add ${field} to complete your profile`;
}

export function ProfileCompletenessCard() {
  const { data: profile, isLoading, isError, refetch } = useProfileCompleteness();
  const [ueiDialogOpen, setUeiDialogOpen] = useState(false);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (!profile) return null;

  const pct = Math.round(profile.completenessPct);
  const progressColor = pct >= 80 ? 'success' : pct >= 50 ? 'warning' : 'error';

  return (
    <>
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, mb: 2 }}>
            <Box sx={{ position: 'relative', display: 'inline-flex' }}>
              <CircularProgress
                variant="determinate"
                value={pct}
                size={80}
                thickness={6}
                color={progressColor}
              />
              <Box
                sx={{
                  top: 0,
                  left: 0,
                  bottom: 0,
                  right: 0,
                  position: 'absolute',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Typography variant="h6" component="div" color="text.secondary">
                  {pct}%
                </Typography>
              </Box>
            </Box>
            <Box>
              <Typography variant="h6">Profile Completeness</Typography>
              <Typography variant="body2" color="text.secondary">
                {profile.organizationName ?? 'Your Organization'}
              </Typography>
            </Box>
          </Box>

          {pct === 100 && (
            <Alert severity="success" sx={{ mb: 2 }}>
              Your organization profile is complete. All fields are populated.
            </Alert>
          )}

          {profile.missingFields.length > 0 && (
            <List dense disablePadding>
              {profile.missingFields.map((field) => (
                <ListItem key={field} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <RadioButtonUncheckedOutlined
                      fontSize="small"
                      color="disabled"
                    />
                  </ListItemIcon>
                  <ListItemText
                    primary={getRecommendation(field)}
                    primaryTypographyProps={{ variant: 'body2' }}
                  />
                </ListItem>
              ))}
            </List>
          )}

          {/* Show completed fields summary */}
          {pct < 100 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Completed:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                {profile.hasUei && <CompletedBadge label="UEI" />}
                {profile.hasCageCode && <CompletedBadge label="CAGE" />}
                {profile.hasNaics && <CompletedBadge label="NAICS" />}
                {profile.hasPsc && <CompletedBadge label="PSC" />}
                {profile.hasCertifications && <CompletedBadge label="Certs" />}
                {profile.hasPastPerformance && <CompletedBadge label="Past Perf" />}
                {profile.hasAddress && <CompletedBadge label="Address" />}
                {profile.hasBusinessType && <CompletedBadge label="Biz Type" />}
                {profile.hasSizeStandard && <CompletedBadge label="Size Std" />}
              </Box>
            </Box>
          )}

          {!profile.hasUei && (
            <Button
              variant="outlined"
              startIcon={<UploadOutlined />}
              onClick={() => setUeiDialogOpen(true)}
              sx={{ mt: 2 }}
            >
              Import from UEI
            </Button>
          )}
        </CardContent>
      </Card>

      <UeiImportDialog
        open={ueiDialogOpen}
        onClose={() => setUeiDialogOpen(false)}
      />
    </>
  );
}

function CompletedBadge({ label }: { label: string }) {
  return (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.5,
        px: 1,
        py: 0.25,
        borderRadius: 1,
        bgcolor: 'success.main',
        color: 'success.contrastText',
        fontSize: '0.7rem',
      }}
    >
      <CheckCircleOutlined sx={{ fontSize: 12 }} />
      {label}
    </Box>
  );
}
