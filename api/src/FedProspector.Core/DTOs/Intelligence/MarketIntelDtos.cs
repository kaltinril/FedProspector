namespace FedProspector.Core.DTOs.Intelligence;

public class MarketShareAnalysisDto
{
    public string NaicsCode { get; set; } = "";
    public string? NaicsDescription { get; set; }
    public int YearsAnalyzed { get; set; }
    public int TotalContracts { get; set; }
    public decimal TotalValue { get; set; }
    public decimal AverageAwardValue { get; set; }
    public List<VendorShareDto> TopVendors { get; set; } = new();
}

public class VendorShareDto
{
    public string? VendorUei { get; set; }
    public string? VendorName { get; set; }
    public int ContractCount { get; set; }
    public decimal TotalValue { get; set; }
    public decimal MarketSharePercent { get; set; }
}

public class IncumbentAnalysisDto
{
    public string NoticeId { get; set; } = "";
    public bool HasIncumbent { get; set; }
    public string? IncumbentUei { get; set; }
    public string? IncumbentName { get; set; }
    // Current contract details
    public string? ContractId { get; set; }
    public decimal? ContractValue { get; set; }
    public decimal? DollarsObligated { get; set; }
    public DateTime? PeriodStart { get; set; }
    public DateTime? PeriodEnd { get; set; }
    public int? MonthsRemaining { get; set; }
    public decimal? MonthlyBurnRate { get; set; }
    public decimal? PercentSpent { get; set; }
    // Incumbent health signals
    public string? RegistrationStatus { get; set; }
    public DateTime? RegistrationExpiration { get; set; }
    public bool IsExcluded { get; set; }
    public string? ExclusionType { get; set; }
    // Incumbent track record
    public int TotalContractsInNaics { get; set; }
    public int ConsecutiveWins { get; set; }
    // Vulnerability assessment
    public List<string> VulnerabilitySignals { get; set; } = new();
    // Fallback competitors when no exact solicitation match
    public bool IsLikelyIncumbent { get; set; }
    public List<LikelyCompetitorDto> LikelyCompetitors { get; set; } = new();
}

public class LikelyCompetitorDto
{
    public string VendorName { get; set; } = "";
    public string? UeiSam { get; set; }
    public int ContractCount { get; set; }
    public decimal TotalValue { get; set; }
}

public class CompetitiveLandscapeDto
{
    public string NaicsCode { get; set; } = "";
    public string AgencyCode { get; set; } = "";
    public string? SetAsideCode { get; set; }
    public int TotalContracts { get; set; }
    public decimal TotalValue { get; set; }
    public decimal AverageAwardValue { get; set; }
    public decimal AgencyAverageAwardValue { get; set; }
    public List<VendorShareDto> TopVendors { get; set; } = new();
    public string CompetitionLevel { get; set; } = "";
    public int DistinctVendorCount { get; set; }
    public string? FallbackScope { get; set; }
}
