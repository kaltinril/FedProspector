using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("organization_certification")]
public class OrganizationCertification
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(50)]
    public string CertificationType { get; set; } = string.Empty;

    [MaxLength(100)]
    public string? CertifyingAgency { get; set; }

    [MaxLength(100)]
    public string? CertificationNumber { get; set; }

    public DateTime? ExpirationDate { get; set; }

    [Required]
    [MaxLength(1)]
    public string IsActive { get; set; } = "Y";

    [Required]
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    // Navigation properties
    public Organization Organization { get; set; } = null!;
}
