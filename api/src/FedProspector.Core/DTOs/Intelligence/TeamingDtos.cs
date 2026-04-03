namespace FedProspector.Core.DTOs.Intelligence;

public class PartnerSearchResultDto
{
    public string UeiSam { get; set; } = string.Empty;
    public string? LegalBusinessName { get; set; }
    public string? State { get; set; }
    public string? NaicsCodes { get; set; }
    public string? PscCodes { get; set; }
    public string? Certifications { get; set; }
    public string? AgenciesWorkedWith { get; set; }
    public string? PerformanceNaicsCodes { get; set; }
    public int ContractCount { get; set; }
    public decimal TotalContractValue { get; set; }
}

public class PartnerRiskDto
{
    public string UeiSam { get; set; } = string.Empty;
    public string? LegalBusinessName { get; set; }
    /// <summary>GREEN, YELLOW, or RED</summary>
    public string RiskLevel { get; set; } = string.Empty;
    public string? RiskSummary { get; set; }
    public bool CurrentExclusionFlag { get; set; }
    public int ExclusionCount { get; set; }
    public int TerminationForCauseCount { get; set; }
    public string? SpendingTrajectory { get; set; }
    public decimal Recent2yrValue { get; set; }
    public decimal Prior2yrValue { get; set; }
    public string? TopAgencyName { get; set; }
    public decimal CustomerConcentrationPct { get; set; }
    public int CertificationCount { get; set; }
    public decimal TotalContractValue { get; set; }
    public decimal? YearsInBusiness { get; set; }
}

public class MentorProtegePairDto
{
    public string ProtegeUei { get; set; } = string.Empty;
    public string? ProtegeName { get; set; }
    public string? ProtegeCertifications { get; set; }
    public string? ProtegeNaics { get; set; }
    public int ProtegeContractCount { get; set; }
    public decimal ProtegeTotalValue { get; set; }
    public string MentorUei { get; set; } = string.Empty;
    public string? MentorName { get; set; }
    public string? SharedNaics { get; set; }
    public int MentorContractCount { get; set; }
    public decimal MentorTotalValue { get; set; }
    public string? MentorAgencies { get; set; }
}

public class PrimeSubRelationshipDto
{
    public string PrimeUei { get; set; } = string.Empty;
    public string? PrimeName { get; set; }
    public string SubUei { get; set; } = string.Empty;
    public string? SubName { get; set; }
    public int SubawardCount { get; set; }
    public decimal? TotalSubawardValue { get; set; }
    public decimal? AvgSubawardValue { get; set; }
    public DateOnly? FirstSubawardDate { get; set; }
    public DateOnly? LastSubawardDate { get; set; }
    public string? NaicsCodesTogether { get; set; }
    public string? AgenciesTogether { get; set; }
}

public class TeamingNetworkNodeDto
{
    public string VendorUei { get; set; } = string.Empty;
    public string? VendorName { get; set; }
    public string RelationshipDirection { get; set; } = string.Empty;
    public string PartnerUei { get; set; } = string.Empty;
    public string? PartnerName { get; set; }
    public int AwardCount { get; set; }
    public decimal? TotalValue { get; set; }
}

public class PartnerGapAnalysisDto
{
    public int OrganizationId { get; set; }
    public List<string> OrgNaicsCodes { get; set; } = [];
    public List<PartnerSearchResultDto> GapFillingPartners { get; set; } = [];
}
