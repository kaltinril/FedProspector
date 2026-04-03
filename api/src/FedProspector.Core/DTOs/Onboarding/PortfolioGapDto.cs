namespace FedProspector.Core.DTOs.Onboarding;

public class PortfolioGapDto
{
    public string NaicsCode { get; set; } = string.Empty;
    public int OpportunityCount { get; set; }
    public int PastPerformanceCount { get; set; }
    public string GapType { get; set; } = string.Empty;
}
