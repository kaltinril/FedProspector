import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  Paper,
  Typography,
  Container,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useAuth } from '@/auth/useAuth';
import { updateProfile, setNaics, setCertifications, createPastPerformance } from '@/api/organization';
import type { OrgNaicsDto, OrgCertificationDto, CreatePastPerformanceRequest } from '@/types/organization';
import { CompanyBasicsStep } from './CompanyBasicsStep';
import type { CompanyBasicsData } from './CompanyBasicsStep';
import { NaicsCodesStep } from './NaicsCodesStep';
import type { NaicsCodeEntry, NaicsStepData } from './NaicsCodesStep';
import { CertificationsStep } from './CertificationsStep';
import type { CertificationEntry } from './CertificationsStep';
import { PastPerformanceStep } from './PastPerformanceStep';
import type { PastPerformanceEntry } from './PastPerformanceStep';
import { ReviewStep } from './ReviewStep';

const STEPS = [
  'Company Basics',
  'NAICS Codes',
  'Certifications',
  'Past Performance',
  'Review & Save',
];

export interface WizardFormData {
  // Step 1
  legalName: string;
  dbaName: string;
  ueiSam: string;
  cageCode: string;
  entityStructure: string;
  addressLine1: string;
  addressLine2: string;
  city: string;
  stateCode: string;
  zipCode: string;
  phone: string;
  website: string;
  // Step 2
  employeeCount: number | null;
  annualRevenue: number | null;
  fiscalYearEndMonth: number;
  naicsCodes: NaicsCodeEntry[];
  // Step 3
  certifications: CertificationEntry[];
  noCertifications: boolean;
  // Step 4
  pastPerformances: PastPerformanceEntry[];
  skipPastPerformance: boolean;
}

const defaultFormData: WizardFormData = {
  legalName: '',
  dbaName: '',
  ueiSam: '',
  cageCode: '',
  entityStructure: '',
  addressLine1: '',
  addressLine2: '',
  city: '',
  stateCode: '',
  zipCode: '',
  phone: '',
  website: '',
  employeeCount: null,
  annualRevenue: null,
  fiscalYearEndMonth: 12,
  naicsCodes: [],
  certifications: [],
  noCertifications: false,
  pastPerformances: [],
  skipPastPerformance: false,
};

export function CompanySetupWizard() {
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState<WizardFormData>(defaultFormData);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const { refreshSession } = useAuth();

  const handleNext = () => setActiveStep((prev) => prev + 1);
  const handleBack = () => setActiveStep((prev) => prev - 1);
  const handleGoToStep = (step: number) => setActiveStep(step);

  // Step 1 complete
  const handleBasicsComplete = (data: CompanyBasicsData) => {
    setFormData((prev) => ({ ...prev, ...data }));
    handleNext();
  };

  // Step 2 data change
  const handleNaicsChange = (data: NaicsStepData) => {
    setFormData((prev) => ({
      ...prev,
      naicsCodes: data.naicsCodes,
      employeeCount: data.employeeCount,
      annualRevenue: data.annualRevenue,
      fiscalYearEndMonth: data.fiscalYearEndMonth,
    }));
  };

  // Step 3 data change
  const handleCertificationsChange = (certs: CertificationEntry[], noCerts: boolean) => {
    setFormData((prev) => ({
      ...prev,
      certifications: certs,
      noCertifications: noCerts,
    }));
  };

  // Step 4 data change
  const handlePastPerformanceChange = (pps: PastPerformanceEntry[], skip: boolean) => {
    setFormData((prev) => ({
      ...prev,
      pastPerformances: pps,
      skipPastPerformance: skip,
    }));
  };

  // Step 5 — save all
  const handleComplete = async () => {
    setIsSaving(true);
    setSaveError(null);

    try {
      // 1. Save profile
      await updateProfile({
        legalName: formData.legalName || null,
        dbaName: formData.dbaName || null,
        ueiSam: formData.ueiSam || null,
        cageCode: formData.cageCode || null,
        entityStructure: formData.entityStructure || null,
        addressLine1: formData.addressLine1 || null,
        addressLine2: formData.addressLine2 || null,
        city: formData.city || null,
        stateCode: formData.stateCode || null,
        zipCode: formData.zipCode || null,
        phone: formData.phone || null,
        website: formData.website || null,
        employeeCount: formData.employeeCount,
        annualRevenue: formData.annualRevenue,
        fiscalYearEndMonth: formData.fiscalYearEndMonth,
        profileCompleted: true,
      });

      // 2. Save NAICS codes
      if (formData.naicsCodes.length > 0) {
        const naicsPayload: OrgNaicsDto[] = formData.naicsCodes.map((n) => ({
          naicsCode: n.naicsCode,
          isPrimary: n.isPrimary,
          sizeStandardMet: n.sizeStandardMet,
        }));
        await setNaics(naicsPayload);
      }

      // 3. Save certifications
      if (formData.certifications.length > 0) {
        const certPayload: OrgCertificationDto[] = formData.certifications.map((c) => ({
          certificationType: c.certificationType,
          certificationNumber: c.certificationNumber || null,
          expirationDate: c.expirationDate || null,
          isActive: true,
        }));
        await setCertifications(certPayload);
      }

      // 4. Save past performance contracts
      if (!formData.skipPastPerformance && formData.pastPerformances.length > 0) {
        for (const pp of formData.pastPerformances) {
          const ppPayload: CreatePastPerformanceRequest = {
            contractNumber: pp.contractNumber || null,
            agencyName: pp.agencyName || null,
            description: pp.description || null,
            naicsCode: pp.naicsCode || null,
            contractValue: pp.contractValue,
            periodStart: pp.periodStart || null,
            periodEnd: pp.periodEnd || null,
          };
          await createPastPerformance(ppPayload);
        }
      }

      // 5. Refresh auth session so the app knows profile is completed
      await refreshSession();

      enqueueSnackbar('Company setup completed successfully!', { variant: 'success' });
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response: { data?: { message?: string } } }).response?.data?.message ??
            'Failed to save. Please try again.')
          : 'An unexpected error occurred. Please try again.';
      setSaveError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const renderStep = () => {
    switch (activeStep) {
      case 0:
        return (
          <CompanyBasicsStep
            data={{
              legalName: formData.legalName,
              dbaName: formData.dbaName,
              ueiSam: formData.ueiSam,
              cageCode: formData.cageCode,
              entityStructure: formData.entityStructure,
              addressLine1: formData.addressLine1,
              addressLine2: formData.addressLine2,
              city: formData.city,
              stateCode: formData.stateCode,
              zipCode: formData.zipCode,
              phone: formData.phone,
              website: formData.website,
            }}
            onNext={handleBasicsComplete}
          />
        );
      case 1:
        return (
          <NaicsCodesStep
            data={{
              naicsCodes: formData.naicsCodes,
              employeeCount: formData.employeeCount,
              annualRevenue: formData.annualRevenue,
              fiscalYearEndMonth: formData.fiscalYearEndMonth,
            }}
            onChange={handleNaicsChange}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 2:
        return (
          <CertificationsStep
            certifications={formData.certifications}
            noCertifications={formData.noCertifications}
            onChange={handleCertificationsChange}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 3:
        return (
          <PastPerformanceStep
            pastPerformances={formData.pastPerformances}
            skipPastPerformance={formData.skipPastPerformance}
            hasUei={!!formData.ueiSam}
            onChange={handlePastPerformanceChange}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 4:
        return (
          <ReviewStep
            data={formData}
            onGoToStep={handleGoToStep}
            onComplete={handleComplete}
            isSaving={isSaving}
            saveError={saveError}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Box sx={{ textAlign: 'center', mb: 4 }}>
        <Typography variant="h4" component="h1" sx={{
          fontWeight: 700
        }}>
          Company Setup
        </Typography>
        <Typography
          variant="body1"
          sx={{
            color: "text.secondary",
            mt: 1
          }}>
          Let&apos;s get your company profile configured for federal contracting.
        </Typography>
      </Box>
      <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>
      <Paper sx={{ p: { xs: 2, sm: 4 } }}>{renderStep()}</Paper>
    </Container>
  );
}
