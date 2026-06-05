import { useEffect, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useSnackbar } from 'notistack';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { useOrganization, useOrgProfile, useUpdateOrgProfile } from '@/queries/useOrganization';
import { useAuth } from '@/auth/useAuth';
import { formatDate } from '@/utils/dateFormatters';
import { ENTITY_STRUCTURES } from '@/utils/constants';
import type { UpdateOrgProfileRequest } from '@/types/organization';
import { OrgNaicsEditor } from './OrgNaicsEditor';
import { OrgCertificationsEditor } from './OrgCertificationsEditor';
import { AssociatedNaicsEditor } from './AssociatedNaicsEditor';

const MONTHS = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
];

/** Editable profile form state — strings for inputs, converted to the request shape on save. */
interface ProfileForm {
  name: string;
  legalName: string;
  dbaName: string;
  ueiSam: string;
  cageCode: string;
  ein: string;
  entityStructure: string;
  addressLine1: string;
  addressLine2: string;
  city: string;
  stateCode: string;
  zipCode: string;
  countryCode: string;
  phone: string;
  website: string;
  fiscalYearEndMonth: string;
  annualRevenue: string;
  employeeCount: string;
}

const EMPTY_FORM: ProfileForm = {
  name: '',
  legalName: '',
  dbaName: '',
  ueiSam: '',
  cageCode: '',
  ein: '',
  entityStructure: '',
  addressLine1: '',
  addressLine2: '',
  city: '',
  stateCode: '',
  zipCode: '',
  countryCode: '',
  phone: '',
  website: '',
  fiscalYearEndMonth: '',
  annualRevenue: '',
  employeeCount: '',
};

export function OrgSettingsTab() {
  const { user } = useAuth();
  const { data: org } = useOrganization();
  const { data: profile, isLoading, isError, refetch } = useOrgProfile();
  const updateProfile = useUpdateOrgProfile();
  const { enqueueSnackbar } = useSnackbar();

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<ProfileForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  // Owner/admin gating — same pattern previously used in this tab.
  const canEdit = user?.role === 'owner' || user?.role === 'admin' || user?.isOrgAdmin === true;

  const buildForm = (): ProfileForm => ({
    name: profile?.name ?? '',
    legalName: profile?.legalName ?? '',
    dbaName: profile?.dbaName ?? '',
    ueiSam: profile?.ueiSam ?? '',
    cageCode: profile?.cageCode ?? '',
    ein: profile?.ein ?? '',
    entityStructure: profile?.entityStructure ?? '',
    addressLine1: profile?.addressLine1 ?? '',
    addressLine2: profile?.addressLine2 ?? '',
    city: profile?.city ?? '',
    stateCode: profile?.stateCode ?? '',
    zipCode: profile?.zipCode ?? '',
    countryCode: profile?.countryCode ?? '',
    phone: profile?.phone ?? '',
    website: profile?.website ?? '',
    fiscalYearEndMonth: profile?.fiscalYearEndMonth != null ? String(profile.fiscalYearEndMonth) : '',
    annualRevenue: profile?.annualRevenue != null ? String(profile.annualRevenue) : '',
    employeeCount: profile?.employeeCount != null ? String(profile.employeeCount) : '',
  });

  // Keep the read-only form in sync with the latest profile when not editing.
  useEffect(() => {
    if (!editing && profile) setForm(buildForm());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, editing]);

  const handleField = (key: keyof ProfileForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleEditStart = () => {
    setForm(buildForm());
    setError(null);
    setEditing(true);
  };

  const handleCancel = () => {
    setEditing(false);
    setError(null);
  };

  const handleSave = () => {
    setError(null);
    const trimmedName = form.name.trim();
    if (!trimmedName) {
      setError('Organization name is required.');
      return;
    }

    // Build a full request. Text fields send '' as null (clears the field); numeric fields
    // parse or send null. UpdateProfileAsync only writes non-null text and HasValue numerics.
    const toNull = (s: string) => (s.trim() === '' ? null : s.trim());
    const toNum = (s: string): number | null => {
      const t = s.trim();
      if (t === '') return null;
      const n = Number(t);
      return Number.isFinite(n) ? n : null;
    };

    const request: UpdateOrgProfileRequest = {
      name: trimmedName,
      legalName: toNull(form.legalName),
      dbaName: toNull(form.dbaName),
      ueiSam: toNull(form.ueiSam),
      cageCode: toNull(form.cageCode),
      ein: toNull(form.ein),
      entityStructure: toNull(form.entityStructure),
      addressLine1: toNull(form.addressLine1),
      addressLine2: toNull(form.addressLine2),
      city: toNull(form.city),
      stateCode: toNull(form.stateCode),
      zipCode: toNull(form.zipCode),
      countryCode: toNull(form.countryCode),
      phone: toNull(form.phone),
      website: toNull(form.website),
      fiscalYearEndMonth: toNum(form.fiscalYearEndMonth),
      annualRevenue: toNum(form.annualRevenue),
      employeeCount: toNum(form.employeeCount),
    };

    updateProfile.mutate(request, {
      onSuccess: () => {
        setEditing(false);
        enqueueSnackbar('Organization profile updated', { variant: 'success' });
      },
      onError: (err) => {
        const msg = err instanceof Error ? err.message : 'Failed to update profile';
        setError(msg);
        enqueueSnackbar('Failed to update profile', { variant: 'error' });
      },
    });
  };

  if (isLoading) return <LoadingState message="Loading organization..." />;
  if (isError) {
    return (
      <ErrorState
        title="Failed to load organization"
        message="Could not retrieve organization details."
        onRetry={() => refetch()}
      />
    );
  }
  if (!profile) return null;

  const disabled = !editing;

  return (
    <Box sx={{ maxWidth: 900 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Organization Profile</Typography>
          {canEdit && !editing && (
            <Button variant="outlined" size="small" onClick={handleEditStart}>
              Edit Profile
            </Button>
          )}
        </Box>

        {/* Identity */}
        <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1 }}>
          Identity
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Organization Name"
              value={form.name}
              onChange={(e) => handleField('name', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
              required
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Legal Name"
              value={form.legalName}
              onChange={(e) => handleField('legalName', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="DBA Name"
              value={form.dbaName}
              onChange={(e) => handleField('dbaName', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              select
              label="Entity Structure"
              value={form.entityStructure}
              onChange={(e) => handleField('entityStructure', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            >
              <MenuItem value="">
                <em>Not set</em>
              </MenuItem>
              {ENTITY_STRUCTURES.map((s) => (
                <MenuItem key={s} value={s}>
                  {s}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              label="UEI (SAM.gov)"
              value={form.ueiSam}
              onChange={(e) => handleField('ueiSam', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              label="CAGE Code"
              value={form.cageCode}
              onChange={(e) => handleField('cageCode', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              label="EIN"
              value={form.ein}
              onChange={(e) => handleField('ein', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 3 }} />

        {/* Address */}
        <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1 }}>
          Address
        </Typography>
        <Grid container spacing={2}>
          <Grid size={12}>
            <TextField
              label="Address Line 1"
              value={form.addressLine1}
              onChange={(e) => handleField('addressLine1', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={12}>
            <TextField
              label="Address Line 2"
              value={form.addressLine2}
              onChange={(e) => handleField('addressLine2', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              label="City"
              value={form.city}
              onChange={(e) => handleField('city', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <TextField
              label="State"
              value={form.stateCode}
              onChange={(e) => handleField('stateCode', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
              slotProps={{ htmlInput: { maxLength: 2 } }}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 2 }}>
            <TextField
              label="ZIP"
              value={form.zipCode}
              onChange={(e) => handleField('zipCode', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              label="Country"
              value={form.countryCode}
              onChange={(e) => handleField('countryCode', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 3 }} />

        {/* Contact */}
        <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1 }}>
          Contact
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Phone"
              value={form.phone}
              onChange={(e) => handleField('phone', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Website"
              value={form.website}
              onChange={(e) => handleField('website', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 3 }} />

        {/* Business Size */}
        <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1 }}>
          Business Size
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          Annual revenue and employee count feed the SBA size-eligibility / pWin scoring.
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              label="Annual Revenue ($)"
              type="number"
              value={form.annualRevenue}
              onChange={(e) => handleField('annualRevenue', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
              slotProps={{ htmlInput: { min: 0, step: 1000 } }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              label="Employee Count"
              type="number"
              value={form.employeeCount}
              onChange={(e) => handleField('employeeCount', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
              slotProps={{ htmlInput: { min: 0, step: 1 } }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              select
              label="Fiscal Year End Month"
              value={form.fiscalYearEndMonth}
              onChange={(e) => handleField('fiscalYearEndMonth', e.target.value)}
              disabled={disabled}
              fullWidth
              size="small"
            >
              <MenuItem value="">
                <em>Not set</em>
              </MenuItem>
              {MONTHS.map((m) => (
                <MenuItem key={m.value} value={String(m.value)}>
                  {m.label}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
        </Grid>

        {editing && (
          <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
            <Button variant="contained" onClick={handleSave} disabled={updateProfile.isPending}>
              Save
            </Button>
            <Button variant="outlined" onClick={handleCancel} disabled={updateProfile.isPending}>
              Cancel
            </Button>
          </Box>
        )}
      </Paper>

      {/* Own NAICS codes (Unit A) */}
      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <OrgNaicsEditor naics={profile.naicsCodes} canEdit={canEdit} />
      </Paper>

      {/* Associated NAICS (Unit G) */}
      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <AssociatedNaicsEditor canEdit={canEdit} />
      </Paper>

      {/* Certifications (Unit A) */}
      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <OrgCertificationsEditor certifications={profile.certifications} canEdit={canEdit} />
      </Paper>

      {/* Read-only org metadata */}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Account
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField label="Slug" value={org?.slug ?? ''} disabled fullWidth size="small" />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Max Users: {org?.maxUsers ?? '-'}
            </Typography>
            {org?.subscriptionTier && (
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Subscription: {org.subscriptionTier}
              </Typography>
            )}
            {org?.createdAt && (
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Created: {formatDate(org.createdAt)}
              </Typography>
            )}
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
}
