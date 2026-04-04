// ============================================================
// Competitive Intelligence types (matching C# DTOs in Intelligence/)
// ============================================================

export interface RecompeteCandidateDto {
  piid: string;
  source: string;
  description?: string | null;
  naicsCode?: string | null;
  setAsideType?: string | null;
  vendorUei?: string | null;
  vendorName?: string | null;
  agencyName?: string | null;
  contractingOfficeId?: string | null;
  contractingOfficeName?: string | null;
  contractValue?: number | null;
  dollarsObligated?: number | null;
  currentEndDate?: string | null;
  dateSigned?: string | null;
  solicitationNumber?: string | null;
  typeOfContractPricing?: string | null;
  extentCompeted?: string | null;
  daysUntilEnd?: number | null;
  incumbentRegistrationStatus?: string | null;
  incumbentRegExpiration?: string | null;
}

export interface AgencyRecompetePatternDto {
  contractingOfficeId: string;
  contractingOfficeName?: string | null;
  agencyName?: string | null;
  incumbentRetentionRatePct?: number | null;
  newVendorPenetrationPct?: number | null;
  setAsideShiftFrequencyPct?: number | null;
  avgSolicitationLeadTimeDays?: number | null;
  bridgeExtensionFrequencyPct?: number | null;
  soleSourceRatePct?: number | null;
  naicsShiftRatePct?: number | null;
  totalContractsAnalyzed: number;
}

export interface CompetitorDossierDto {
  ueiSam: string;
  legalBusinessName?: string | null;
  dbaName?: string | null;
  registrationStatus?: string | null;
  registrationExpirationDate?: string | null;
  primaryNaics?: string | null;
  entityUrl?: string | null;
  registeredNaicsCodes?: string | null;
  sbaCertifications?: string | null;
  businessTypeCodes?: string | null;
  // FPDS metrics
  fpdsContractCount: number;
  fpdsTotalObligated?: number | null;
  fpdsObligated3yr?: number | null;
  fpdsObligated5yr?: number | null;
  fpdsCount3yr?: number | null;
  fpdsCount5yr?: number | null;
  fpdsAvgContractValue?: number | null;
  fpdsMostRecentAward?: string | null;
  fpdsTopNaics?: string | null;
  fpdsTopAgencies?: string | null;
  // USASpending metrics
  usaContractCount: number;
  usaTotalObligated?: number | null;
  usaObligated3yr?: number | null;
  usaObligated5yr?: number | null;
  usaMostRecentAward?: string | null;
  usaTopAgencies?: string | null;
  // Subcontracting
  subContractCount: number;
  subTotalValue?: number | null;
  subAvgValue?: number | null;
  primeSubAwardsCount: number;
  primeSubTotalValue?: number | null;
}

export interface AgencyBuyingPatternDto {
  agencyId: string;
  agencyName?: string | null;
  awardYear: number;
  awardQuarter: number;
  contractCount: number;
  totalObligated?: number | null;
  // Set-aside percentages
  smallBusinessPct?: number | null;
  wosbPct?: number | null;
  eightAPct?: number | null;
  hubzonePct?: number | null;
  sdvosbPct?: number | null;
  unrestrictedPct?: number | null;
  // Competition percentages
  fullCompetitionPct?: number | null;
  soleSourcePct?: number | null;
  limitedCompetitionPct?: number | null;
  // Contract type percentages
  ffpPct?: number | null;
  tmPct?: number | null;
  costPlusPct?: number | null;
  otherTypePct?: number | null;
}

export interface ContractingOfficeProfileDto {
  contractingOfficeId: string;
  contractingOfficeName?: string | null;
  agencyName?: string | null;
  totalAwards: number;
  totalObligated?: number | null;
  avgAwardValue?: number | null;
  earliestAward?: string | null;
  latestAward?: string | null;
  topNaicsCodes?: string | null;
  // Set-aside preferences
  smallBusinessPct?: number | null;
  wosbPct?: number | null;
  eightAPct?: number | null;
  hubzonePct?: number | null;
  sdvosbPct?: number | null;
  unrestrictedPct?: number | null;
  // Contract type distribution
  ffpPct?: number | null;
  tmPct?: number | null;
  costPlusPct?: number | null;
  // Competition preference
  fullCompetitionPct?: number | null;
  soleSourcePct?: number | null;
  avgProcurementDays?: number | null;
}

// Search params
export interface RecompeteCandidateSearchParams {
  naicsCode?: string;
  agencyCode?: string;
  setAsideCode?: string;
  page?: number;
  pageSize?: number;
}

export interface AgencyPatternSearchParams {
  agencyCode?: string;
  officeCode?: string;
}

export interface OfficeSearchParams {
  agencyCode?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}
