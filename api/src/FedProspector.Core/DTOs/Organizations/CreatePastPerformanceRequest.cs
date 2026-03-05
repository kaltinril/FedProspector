using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Organizations;

public class CreatePastPerformanceRequest
{
    [MaxLength(50)]
    public string? ContractNumber { get; set; }

    [MaxLength(200)]
    public string? AgencyName { get; set; }

    public string? Description { get; set; }

    [MaxLength(11)]
    public string? NaicsCode { get; set; }

    public decimal? ContractValue { get; set; }

    public DateTime? PeriodStart { get; set; }

    public DateTime? PeriodEnd { get; set; }
}
