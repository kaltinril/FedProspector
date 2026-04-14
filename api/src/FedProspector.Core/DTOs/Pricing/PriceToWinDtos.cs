namespace FedProspector.Core.DTOs.Pricing;

public class PriceToWinRequest
{
    public string? NaicsCode { get; set; }
    public string? AgencyName { get; set; }
    public string? SetAsideType { get; set; }
    public string? ContractType { get; set; }
    public string? EstimatedScope { get; set; }
    /// <summary>FPDS source selection code (e.g. "LPTA", "BV"). Filters comparables to matching regime.</summary>
    public string? SourceSelectionCode { get; set; }
    /// <summary>FPDS type of contract pricing (e.g. "FFP", "T&amp;M", "CR"). Filters comparables to matching pricing type.</summary>
    public string? ContractPricingType { get; set; }
}

public class PriceToWinResponse
{
    public decimal LowEstimate { get; set; }
    public decimal TargetEstimate { get; set; }
    public decimal HighEstimate { get; set; }
    public decimal Confidence { get; set; }
    public int ComparableCount { get; set; }
    /// <summary>Source selection regime used for the estimate (e.g. "LPTA", "BV"), or null if not filtered.</summary>
    public string? SourceSelectionRegime { get; set; }
    /// <summary>True if FPDS filters reduced the comparable set below threshold and the estimate fell back to unfiltered data.</summary>
    public bool FilterFallback { get; set; }
    public List<ComparableAwardDto> ComparableAwards { get; set; } = new();
    public CompetitionStatsDto CompetitionStats { get; set; } = new();
}

public class ComparableAwardDto
{
    public string ContractId { get; set; } = "";
    public string? Vendor { get; set; }
    public decimal? AwardValue { get; set; }
    public int? Offers { get; set; }
    public string? Agency { get; set; }
    public DateOnly? AwardDate { get; set; }
    public int? PopMonths { get; set; }
}

public class CompetitionStatsDto
{
    public decimal AvgOffers { get; set; }
    public decimal MedianOffers { get; set; }
    public decimal SoloSourcePct { get; set; }
    public decimal AvgAwardValue { get; set; }
    public decimal MedianAwardValue { get; set; }
}
