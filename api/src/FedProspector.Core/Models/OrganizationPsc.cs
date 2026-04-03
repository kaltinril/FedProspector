using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("organization_psc")]
public class OrganizationPsc
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    [Column("organization_psc_id")]
    public int OrganizationPscId { get; set; }

    [Required]
    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(10)]
    [Column("psc_code")]
    public string PscCode { get; set; } = string.Empty;

    [Column("added_at")]
    public DateTime? AddedAt { get; set; }

    // Navigation properties
    public Organization Organization { get; set; } = null!;
}
