namespace FedProspector.Core.DTOs.Prospects;

public class ProspectOpportunityDto
{
    public string? Title { get; set; }
    public string? SolicitationNumber { get; set; }
    public string? DepartmentName { get; set; }
    public string? SubTier { get; set; }
    public string? Office { get; set; }
    public string? ContractingOfficeId { get; set; }
    public DateOnly? PostedDate { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public string? Type { get; set; }
    public string? SetAsideCode { get; set; }
    public string? SetAsideDescription { get; set; }
    public string? NaicsCode { get; set; }
    public string? PopState { get; set; }
    public string? PopZip { get; set; }
    public string? PopCountry { get; set; }
    public string? Active { get; set; }
    public decimal? AwardAmount { get; set; }
    public string? Link { get; set; }
}
