using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Onboarding;

public class UeiImportRequest
{
    [Required]
    [MaxLength(13)]
    public string Uei { get; set; } = string.Empty;
}
