namespace FedProspector.Core.DTOs.Intelligence;

public class CompetitorAnalysisDto
{
    public string? NaicsCode { get; set; }
    public string? NoticeId { get; set; }
    public string? AgencyCode { get; set; }
    public int TotalCompetitorsFound { get; set; }
    public List<CompetitorScoreDto> Competitors { get; set; } = new();
}

public class CompetitorScoreDto
{
    public string VendorUei { get; set; } = "";
    public string VendorName { get; set; } = "";
    public int CsiScore { get; set; }
    public string Category { get; set; } = "";
    public string Confidence { get; set; } = "Medium";
    public int DataCompletenessPercent { get; set; }
    public List<CsiFactorDto> Factors { get; set; } = new();
    public int ContractCount { get; set; }
    public decimal TotalValue { get; set; }
    public decimal MarketSharePercent { get; set; }
}

public class CsiFactorDto
{
    public string Name { get; set; } = "";
    public int Score { get; set; }
    public decimal Weight { get; set; }
    public decimal WeightedScore { get; set; }
    public string Detail { get; set; } = "";
    public bool HadRealData { get; set; } = true;
}
