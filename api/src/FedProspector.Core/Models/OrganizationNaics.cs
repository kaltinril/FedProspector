using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("organization_naics")]
public class OrganizationNaics
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(11)]
    public string NaicsCode { get; set; } = string.Empty;

    [Required]
    [MaxLength(1)]
    public string IsPrimary { get; set; } = "N";

    [Required]
    [MaxLength(1)]
    public string SizeStandardMet { get; set; } = "N";

    [Required]
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    // Navigation properties
    public Organization Organization { get; set; } = null!;
}
