using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Onboarding;

public class UeiImportRequest
{
    [Required]
    [MinLength(12)]
    [MaxLength(12)]
    public string Uei { get; set; } = string.Empty;
}
