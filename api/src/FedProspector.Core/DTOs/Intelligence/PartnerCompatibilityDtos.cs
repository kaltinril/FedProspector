namespace FedProspector.Core.DTOs.Intelligence;

public class PartnerAnalysisDto
{
    public string NoticeId { get; set; } = "";
    public int OrgId { get; set; }
    public int TotalPartnersFound { get; set; }
    public List<PartnerScoreDto> Partners { get; set; } = new();
}

public class PartnerScoreDto
{
    public string PartnerUei { get; set; } = "";
    public string PartnerName { get; set; } = "";
    public int PcsScore { get; set; }
    public string Category { get; set; } = "";
    public string Confidence { get; set; } = "Medium";
    public int DataCompletenessPercent { get; set; }
    public List<PcsFactorDto> Factors { get; set; } = new();
    public int PastTeamingCount { get; set; }
    public int AgencyAwardCount { get; set; }
}

public class PcsFactorDto
{
    public string Name { get; set; } = "";
    public int Score { get; set; }
    public decimal Weight { get; set; }
    public decimal WeightedScore { get; set; }
    public string Detail { get; set; } = "";
    public bool HadRealData { get; set; } = true;
}
