import { useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Box,
  Grid,
  TextField,
  Button,
  MenuItem,
  Typography,
  Alert,
  CircularProgress,
  InputAdornment,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { ENTITY_STRUCTURES } from '@/utils/constants';
import { getEntity } from '@/api/entities';

const US_STATES = [
  { value: 'AL', label: 'Alabama' },
  { value: 'AK', label: 'Alaska' },
  { value: 'AZ', label: 'Arizona' },
  { value: 'AR', label: 'Arkansas' },
  { value: 'CA', label: 'California' },
  { value: 'CO', label: 'Colorado' },
  { value: 'CT', label: 'Connecticut' },
  { value: 'DE', label: 'Delaware' },
  { value: 'DC', label: 'District of Columbia' },
  { value: 'FL', label: 'Florida' },
  { value: 'GA', label: 'Georgia' },
  { value: 'HI', label: 'Hawaii' },
  { value: 'ID', label: 'Idaho' },
  { value: 'IL', label: 'Illinois' },
  { value: 'IN', label: 'Indiana' },
  { value: 'IA', label: 'Iowa' },
  { value: 'KS', label: 'Kansas' },
  { value: 'KY', label: 'Kentucky' },
  { value: 'LA', label: 'Louisiana' },
  { value: 'ME', label: 'Maine' },
  { value: 'MD', label: 'Maryland' },
  { value: 'MA', label: 'Massachusetts' },
  { value: 'MI', label: 'Michigan' },
  { value: 'MN', label: 'Minnesota' },
  { value: 'MS', label: 'Mississippi' },
  { value: 'MO', label: 'Missouri' },
  { value: 'MT', label: 'Montana' },
  { value: 'NE', label: 'Nebraska' },
  { value: 'NV', label: 'Nevada' },
  { value: 'NH', label: 'New Hampshire' },
  { value: 'NJ', label: 'New Jersey' },
  { value: 'NM', label: 'New Mexico' },
  { value: 'NY', label: 'New York' },
  { value: 'NC', label: 'North Carolina' },
  { value: 'ND', label: 'North Dakota' },
  { value: 'OH', label: 'Ohio' },
  { value: 'OK', label: 'Oklahoma' },
  { value: 'OR', label: 'Oregon' },
  { value: 'PA', label: 'Pennsylvania' },
  { value: 'PR', label: 'Puerto Rico' },
  { value: 'RI', label: 'Rhode Island' },
  { value: 'SC', label: 'South Carolina' },
  { value: 'SD', label: 'South Dakota' },
  { value: 'TN', label: 'Tennessee' },
  { value: 'TX', label: 'Texas' },
  { value: 'UT', label: 'Utah' },
  { value: 'VT', label: 'Vermont' },
  { value: 'VA', label: 'Virginia' },
  { value: 'VI', label: 'Virgin Islands' },
  { value: 'WA', label: 'Washington' },
  { value: 'WV', label: 'West Virginia' },
  { value: 'WI', label: 'Wisconsin' },
  { value: 'WY', label: 'Wyoming' },
];

const basicsSchema = z.object({
  legalName: z.string().min(1, 'Legal name is required').max(300),
  dbaName: z.string().max(300).optional().or(z.literal('')),
  ueiSam: z
    .string()
    .max(13)
    .regex(/^[A-Za-z0-9]*$/, 'UEI must be alphanumeric')
    .optional()
    .or(z.literal('')),
  cageCode: z.string().max(5).optional().or(z.literal('')),
  entityStructure: z.string().min(1, 'Entity structure is required'),
  addressLine1: z.string().min(1, 'Address is required').max(200),
  addressLine2: z.string().max(200).optional().or(z.literal('')),
  city: z.string().min(1, 'City is required').max(100),
  stateCode: z.string().min(1, 'State is required').max(2),
  zipCode: z.string().min(1, 'ZIP code is required').max(10),
  phone: z.string().max(20).optional().or(z.literal('')),
  website: z.string().max(500).optional().or(z.literal('')),
});

export type CompanyBasicsData = z.infer<typeof basicsSchema>;

interface CompanyBasicsStepProps {
  data: CompanyBasicsData;
  onNext: (data: CompanyBasicsData) => void;
}

export function CompanyBasicsStep({ data, onNext }: CompanyBasicsStepProps) {
  const [ueiLookupStatus, setUeiLookupStatus] = useState<
    'idle' | 'loading' | 'found' | 'not-found' | 'error'
  >('idle');
  const [ueiEntityName, setUeiEntityName] = useState('');

  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<CompanyBasicsData>({
    resolver: zodResolver(basicsSchema),
    defaultValues: data,
  });

  const ueiValue = watch('ueiSam');

  const handleUeiLookup = async () => {
    if (!ueiValue || ueiValue.length < 2) return;
    setUeiLookupStatus('loading');
    try {
      const entity = await getEntity(ueiValue);
      setUeiEntityName(entity.legalBusinessName ?? ueiValue);
      setUeiLookupStatus('found');
    } catch {
      setUeiLookupStatus('not-found');
      setUeiEntityName('');
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onNext)} noValidate>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Company Information
      </Typography>

      <Grid container spacing={2}>
        {/* Name Section */}
        <Grid size={{ xs: 12, sm: 6 }}>
          <TextField
            {...register('legalName')}
            label="Legal Name"
            required
            fullWidth
            error={!!errors.legalName}
            helperText={errors.legalName?.message}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <TextField
            {...register('dbaName')}
            label="DBA Name"
            fullWidth
            error={!!errors.dbaName}
            helperText={errors.dbaName?.message}
          />
        </Grid>

        {/* Identifiers Section */}
        <Grid size={{ xs: 12, sm: 6 }}>
          <TextField
            {...register('ueiSam')}
            label="UEI (SAM.gov)"
            fullWidth
            error={!!errors.ueiSam}
            helperText={errors.ueiSam?.message}
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    <Button
                      size="small"
                      onClick={handleUeiLookup}
                      disabled={!ueiValue || ueiValue.length < 2 || ueiLookupStatus === 'loading'}
                      startIcon={
                        ueiLookupStatus === 'loading' ? (
                          <CircularProgress size={16} />
                        ) : (
                          <SearchIcon />
                        )
                      }
                    >
                      Look Up
                    </Button>
                  </InputAdornment>
                ),
              },
            }}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <TextField
            {...register('cageCode')}
            label="CAGE Code"
            fullWidth
            error={!!errors.cageCode}
            helperText={errors.cageCode?.message}
          />
        </Grid>

        {ueiLookupStatus === 'found' && (
          <Grid size={12}>
            <Alert severity="success" icon={<CheckCircleIcon />}>
              Entity found: {ueiEntityName}
            </Alert>
          </Grid>
        )}
        {ueiLookupStatus === 'not-found' && (
          <Grid size={12}>
            <Alert severity="warning">
              No entity found for this UEI. You can still proceed — verify the UEI is correct.
            </Alert>
          </Grid>
        )}
        {ueiLookupStatus === 'error' && (
          <Grid size={12}>
            <Alert severity="error">Unable to look up UEI. Please try again later.</Alert>
          </Grid>
        )}

        {/* Entity Structure */}
        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="entityStructure"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                select
                label="Entity Structure"
                required
                fullWidth
                error={!!errors.entityStructure}
                helperText={errors.entityStructure?.message}
              >
                {ENTITY_STRUCTURES.map((s) => (
                  <MenuItem key={s} value={s}>
                    {s}
                  </MenuItem>
                ))}
              </TextField>
            )}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }} />

        {/* Address Section */}
        <Grid size={12}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1 }}>
            Business Address
          </Typography>
        </Grid>
        <Grid size={12}>
          <TextField
            {...register('addressLine1')}
            label="Address Line 1"
            required
            fullWidth
            error={!!errors.addressLine1}
            helperText={errors.addressLine1?.message}
          />
        </Grid>
        <Grid size={12}>
          <TextField
            {...register('addressLine2')}
            label="Address Line 2"
            fullWidth
            error={!!errors.addressLine2}
            helperText={errors.addressLine2?.message}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <TextField
            {...register('city')}
            label="City"
            required
            fullWidth
            error={!!errors.city}
            helperText={errors.city?.message}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Controller
            name="stateCode"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                select
                label="State"
                required
                fullWidth
                error={!!errors.stateCode}
                helperText={errors.stateCode?.message}
              >
                {US_STATES.map((s) => (
                  <MenuItem key={s.value} value={s.value}>
                    {s.label}
                  </MenuItem>
                ))}
              </TextField>
            )}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <TextField
            {...register('zipCode')}
            label="ZIP Code"
            required
            fullWidth
            error={!!errors.zipCode}
            helperText={errors.zipCode?.message}
          />
        </Grid>

        {/* Contact Section */}
        <Grid size={12}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1 }}>
            Contact Information
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <TextField
            {...register('phone')}
            label="Phone"
            fullWidth
            error={!!errors.phone}
            helperText={errors.phone?.message}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <TextField
            {...register('website')}
            label="Website"
            fullWidth
            error={!!errors.website}
            helperText={errors.website?.message}
          />
        </Grid>
      </Grid>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
        <Button type="submit" variant="contained" size="large">
          Next
        </Button>
      </Box>
    </Box>
  );
}
