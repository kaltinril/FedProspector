// ============================================================
// Onboarding & Past Performance types (matching C# DTOs in Onboarding/)
// ============================================================

export interface ProfileCompletenessDto {
  organizationId: number;
  organizationName?: string | null;
  completenessPct: number;
  hasUei: boolean;
  hasCageCode: boolean;
  hasNaics: boolean;
  hasPsc: boolean;
  hasCertifications: boolean;
  hasPastPerformance: boolean;
  hasAddress: boolean;
  hasBusinessType: boolean;
  hasSizeStandard: boolean;
  missingFields: string[];
}

export interface UeiImportResultDto {
  uei: string;
  entityFound: boolean;
  fieldsPopulated: string[];
  naicsCodesImported: number;
  certificationsImported: number;
  message?: string | null;
}

export interface CertificationAlertDto {
  certificationType: string;
  expirationDate: string;
  daysUntilExpiration: number;
  alertLevel: string;
  source: string;
}

export interface SizeStandardAlertDto {
  naicsCode: string;
  sizeStandardType?: string | null;
  threshold?: number | null;
  currentValue?: number | null;
  pctOfThreshold?: number | null;
}

export interface PastPerformanceRelevanceDto {
  pastPerformanceId: number;
  contractNumber?: string | null;
  ppAgency?: string | null;
  ppNaics?: string | null;
  ppValue?: number | null;
  noticeId: string;
  opportunityTitle?: string | null;
  oppAgency?: string | null;
  oppNaics?: string | null;
  oppValue?: number | null;
  naicsMatch: boolean;
  agencyMatch: boolean;
  valueSimilarity?: number | null;
  yearsSinceCompletion?: number | null;
  relevanceScore?: number | null;
}

export interface PortfolioGapDto {
  naicsCode: string;
  opportunityCount: number;
  pastPerformanceCount: number;
  gapType: string;
}

export interface OrganizationPscDto {
  organizationPscId: number;
  pscCode: string;
  addedAt?: string | null;
}
