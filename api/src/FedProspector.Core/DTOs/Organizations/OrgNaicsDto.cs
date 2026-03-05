using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Organizations;

public class OrgNaicsDto
{
    public int? Id { get; set; }

    [Required]
    [MaxLength(11)]
    public string NaicsCode { get; set; } = string.Empty;

    public bool IsPrimary { get; set; }
    public bool SizeStandardMet { get; set; }
}
