// ============================================================
// Teaming & Partnership Intelligence types (matching C# DTOs in Intelligence/)
// ============================================================

export interface PartnerSearchResultDto {
  ueiSam: string;
  legalBusinessName?: string | null;
  state?: string | null;
  naicsCodes?: string | null;
  pscCodes?: string | null;
  certifications?: string | null;
  agenciesWorkedWith?: string | null;
  performanceNaicsCodes?: string | null;
  contractCount: number;
  totalContractValue: number;
}

export interface PartnerRiskDto {
  ueiSam: string;
  legalBusinessName?: string | null;
  riskLevel: string;
  riskSummary?: string | null;
  currentExclusionFlag: boolean;
  exclusionCount: number;
  terminationForCauseCount: number;
  spendingTrajectory?: string | null;
  recent2yrValue: number;
  prior2yrValue: number;
  topAgencyName?: string | null;
  customerConcentrationPct: number;
  certificationCount: number;
  totalContractValue: number;
  yearsInBusiness?: number | null;
}

export interface MentorProtegePairDto {
  protegeUei: string;
  protegeName?: string | null;
  protegeCertifications?: string | null;
  protegeNaics?: string | null;
  protegeContractCount: number;
  protegeTotalValue: number;
  mentorUei: string;
  mentorName?: string | null;
  sharedNaics?: string | null;
  mentorContractCount: number;
  mentorTotalValue: number;
  mentorAgencies?: string | null;
}

export interface PrimeSubRelationshipDto {
  primeUei: string;
  primeName?: string | null;
  subUei: string;
  subName?: string | null;
  subawardCount: number;
  totalSubawardValue?: number | null;
  avgSubawardValue?: number | null;
  firstSubawardDate?: string | null;
  lastSubawardDate?: string | null;
  naicsCodesTogether?: string | null;
  agenciesTogether?: string | null;
}

export interface TeamingNetworkNodeDto {
  vendorUei: string;
  vendorName?: string | null;
  relationshipDirection: string;
  partnerUei: string;
  partnerName?: string | null;
  awardCount: number;
  totalValue?: number | null;
}

export interface PartnerGapAnalysisDto {
  organizationId: number;
  orgNaicsCodes: string[];
  gapFillingPartners: PartnerSearchResultDto[];
}

// Search params
export interface PartnerSearchParams {
  naicsCode?: string;
  state?: string;
  certification?: string;
  agencyCode?: string;
  page?: number;
  pageSize?: number;
}

export interface MentorProtegeSearchParams {
  protegeUei?: string;
  naicsCode?: string;
  page?: number;
  pageSize?: number;
}
