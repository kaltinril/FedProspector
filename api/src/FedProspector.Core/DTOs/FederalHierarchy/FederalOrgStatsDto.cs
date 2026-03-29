namespace FedProspector.Core.DTOs.FederalHierarchy;

public class FederalOrgStatsDto
{
    public int OpportunityCount { get; set; }
    public int OpenOpportunityCount { get; set; }
    public int AwardCount { get; set; }
    public decimal TotalAwardDollars { get; set; }
    public List<NaicsBreakdownItem> TopNaicsCodes { get; set; } = [];
    public List<SetAsideBreakdownItem> SetAsideBreakdown { get; set; } = [];
}

public class NaicsBreakdownItem
{
    public string Code { get; set; } = string.Empty;
    public int Count { get; set; }
}

public class SetAsideBreakdownItem
{
    public string Type { get; set; } = string.Empty;
    public int Count { get; set; }
}
