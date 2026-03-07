namespace FedProspector.Core.DTOs.Opportunities;

public class OpportunityDetailDto
{
    // Core fields
    public string NoticeId { get; set; } = string.Empty;
    public string? Title { get; set; }
    public string? SolicitationNumber { get; set; }
    public string? DepartmentName { get; set; }
    public string? SubTier { get; set; }
    public string? Office { get; set; }
    public DateOnly? PostedDate { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public DateOnly? ArchiveDate { get; set; }
    public string? Type { get; set; }
    public string? BaseType { get; set; }
    public string? SetAsideCode { get; set; }
    public string? SetAsideDescription { get; set; }
    public string? ClassificationCode { get; set; }
    public string? NaicsCode { get; set; }
    public string? NaicsDescription { get; set; }
    public string? NaicsSector { get; set; }
    public string? SizeStandard { get; set; }
    public string? SetAsideCategory { get; set; }
    public string? PopState { get; set; }
    public string? PopZip { get; set; }
    public string? PopCountry { get; set; }
    public string? PopCity { get; set; }
    public string? Active { get; set; }
    public string? AwardNumber { get; set; }
    public DateOnly? AwardDate { get; set; }
    public decimal? AwardAmount { get; set; }
    public string? AwardeeUei { get; set; }
    public string? AwardeeName { get; set; }
    public string? DescriptionUrl { get; set; }
    public string? Link { get; set; }
    public string? ResourceLinks { get; set; }
    public List<ResourceLinkDto> ResourceLinkDetails { get; set; } = [];
    public decimal? EstimatedContractValue { get; set; }
    public string? SecurityClearanceRequired { get; set; }
    public string? IncumbentUei { get; set; }
    public string? IncumbentName { get; set; }
    public DateOnly? PeriodOfPerformanceStart { get; set; }
    public DateOnly? PeriodOfPerformanceEnd { get; set; }
    public DateTime? FirstLoadedAt { get; set; }
    public DateTime? LastLoadedAt { get; set; }

    // Nested
    public List<RelatedAwardDto> RelatedAwards { get; set; } = [];
    public ProspectSummaryDto? Prospect { get; set; }
    public UsaspendingSummaryDto? UsaspendingAward { get; set; }
}

public class RelatedAwardDto
{
    public string ContractId { get; set; } = string.Empty;
    public string? VendorName { get; set; }
    public string? VendorUei { get; set; }
    public DateOnly? DateSigned { get; set; }
    public decimal? DollarsObligated { get; set; }
    public decimal? BaseAndAllOptions { get; set; }
    public string? TypeOfContract { get; set; }
    public int? NumberOfOffers { get; set; }
}

public class ProspectSummaryDto
{
    public int ProspectId { get; set; }
    public string Status { get; set; } = string.Empty;
    public string? Priority { get; set; }
    public decimal? GoNoGoScore { get; set; }
    public decimal? WinProbability { get; set; }
    public string? AssignedTo { get; set; }
}

public class UsaspendingSummaryDto
{
    public string GeneratedUniqueAwardId { get; set; } = string.Empty;
    public string? RecipientName { get; set; }
    public string? RecipientUei { get; set; }
    public decimal? TotalObligation { get; set; }
    public decimal? BaseAndAllOptionsValue { get; set; }
    public DateOnly? StartDate { get; set; }
    public DateOnly? EndDate { get; set; }
}
