using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("organization_entity")]
public class OrganizationEntity
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(13)]
    public string? PartnerUei { get; set; }

    [Required]
    [MaxLength(20)]
    public string Relationship { get; set; } = string.Empty;

    [Required]
    [MaxLength(1)]
    public string IsActive { get; set; } = "Y";

    public int? AddedBy { get; set; }

    public string? Notes { get; set; }

    [Required]
    public DateTime CreatedAt { get; set; }

    [Required]
    public DateTime UpdatedAt { get; set; }

    // Navigation properties
    [ForeignKey("OrganizationId")]
    public Organization? Organization { get; set; }

    [ForeignKey("UeiSam")]
    public Entity? Entity { get; set; }

    [ForeignKey("AddedBy")]
    public AppUser? AddedByUser { get; set; }
}
