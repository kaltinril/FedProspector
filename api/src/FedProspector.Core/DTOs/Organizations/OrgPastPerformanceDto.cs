namespace FedProspector.Core.DTOs.Organizations;

public class OrgPastPerformanceDto
{
    public int Id { get; set; }
    public string? ContractNumber { get; set; }
    public string? AgencyName { get; set; }
    public string? Description { get; set; }
    public string? NaicsCode { get; set; }
    public decimal? ContractValue { get; set; }
    public DateTime? PeriodStart { get; set; }
    public DateTime? PeriodEnd { get; set; }
    public DateTime CreatedAt { get; set; }
}
