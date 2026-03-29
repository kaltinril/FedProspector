namespace FedProspector.Core.DTOs.Opportunities;

public class OpportunitySearchDto
{
    public string NoticeId { get; set; } = string.Empty;
    public string? Title { get; set; }
    public string? SolicitationNumber { get; set; }
    public string? DepartmentName { get; set; }
    public string? Office { get; set; }
    public string? ContractingOfficeId { get; set; }
    public DateOnly? PostedDate { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public int? DaysUntilDue { get; set; }
    public string? SetAsideCode { get; set; }
    public string? SetAsideDescription { get; set; }
    public string? SetAsideCategory { get; set; }
    public string? NaicsCode { get; set; }
    public string? NaicsDescription { get; set; }
    public string? NaicsSector { get; set; }
    public string? SizeStandard { get; set; }
    public decimal? BaseAndAllOptions { get; set; }
    public decimal? EstimatedContractValue { get; set; }
    public string? PopState { get; set; }
    public string? PopStateName { get; set; }
    public string? PopCity { get; set; }
    public string? PopCountry { get; set; }
    public string? PopCountryName { get; set; }
    public string? ProspectStatus { get; set; }
    public string? AssignedUser { get; set; }
}
