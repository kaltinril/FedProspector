namespace FedProspector.Core.Models.Views;

public class ProcurementIntelligenceView
{
    public string NoticeId { get; set; } = string.Empty;
    public string? SolicitationNumber { get; set; }
    public string? Title { get; set; }
    public string? OpportunityType { get; set; }
    public string? SetAsideCode { get; set; }
    public string? NaicsCode { get; set; }
    public DateOnly? PostedDate { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public string? DepartmentName { get; set; }
    public string? SubTier { get; set; }
    public string? Office { get; set; }
    public string? AwardNumber { get; set; }
    public decimal? OppAwardAmount { get; set; }
    public DateOnly? AwardDate { get; set; }
    public string? SamGovLink { get; set; }

    // FPDS fields
    public string? Piid { get; set; }
    public string? AwardeeName { get; set; }
    public string? AwardeeUei { get; set; }
    public int? BidderCount { get; set; }
    public string? ExtentCompeted { get; set; }
    public decimal? DollarsObligated { get; set; }
    public decimal? ContractCeiling { get; set; }
    public DateOnly? DateSigned { get; set; }
    public DateOnly? EffectiveDate { get; set; }
    public DateOnly? CompletionDate { get; set; }
    public DateOnly? UltimateCompletionDate { get; set; }
    public string? TypeOfContract { get; set; }
    public string? TypeOfContractPricing { get; set; }

    // USASpending fields
    public decimal? TotalSpent { get; set; }
    public decimal? UsaCeiling { get; set; }
    public DateOnly? PerformanceStart { get; set; }
    public DateOnly? PerformanceEnd { get; set; }
    public string? IncumbentName { get; set; }
    public string? IncumbentUei { get; set; }

    // Computed
    public int? TotalPerformanceDays { get; set; }
    public decimal? MonthlyBurnRate { get; set; }
}
