using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Organizations;

public class OrgCertificationDto
{
    public int? Id { get; set; }

    [Required]
    [MaxLength(50)]
    public string CertificationType { get; set; } = string.Empty;

    [MaxLength(100)]
    public string? CertifyingAgency { get; set; }

    [MaxLength(100)]
    public string? CertificationNumber { get; set; }

    public DateTime? ExpirationDate { get; set; }

    public bool IsActive { get; set; } = true;

    public string? Source { get; set; }
}
