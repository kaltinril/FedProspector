export interface SimilarOpportunityDto {
  matchNoticeId: string;
  matchTitle: string | null;
  matchAgency: string | null;
  matchNaics: string | null;
  matchSetAside: string | null;
  matchValue: number | null;
  matchPostedDate: string | null;
  matchResponseDeadline: string | null;
  similarityFactors: string | null;
  similarityScore: number;
}

export interface CrossSourceValidationDto {
  checkId: string;
  checkName: string;
  sourceAName: string;
  sourceACount: number;
  sourceBName: string;
  sourceBCount: number;
  difference: number;
  pctDifference: number;
  status: string;
}

export interface DataFreshnessDto {
  sourceName: string;
  lastLoadDate: string | null;
  recordsLoaded: number;
  lastLoadStatus: string | null;
  hoursSinceLastLoad: number | null;
  freshnessStatus: string;
  tableRowCount: number | null;
  tableName: string | null;
}

export interface DataCompletenessDto {
  tableName: string;
  totalRows: number;
  fieldName: string;
  nonNullCount: number;
  nullCount: number;
  completenessPct: number;
}

export interface ProspectCompetitorSummaryDto {
  prospectId: number;
  noticeId: string;
  opportunityTitle: string | null;
  naicsCode: string | null;
  departmentName: string | null;
  setAsideCode: string | null;
  likelyIncumbent: string | null;
  incumbentUei: string | null;
  incumbentContractValue: number | null;
  incumbentContractEnd: string | null;
  estimatedCompetitorCount: number;
}

export interface DataQualityDashboardDto {
  freshness: DataFreshnessDto[];
  completeness: DataCompletenessDto[];
  validation: CrossSourceValidationDto[];
}
