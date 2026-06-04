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

    // --- Phase 133 Task 6: SBA affiliation size roll-up (13 CFR 121.103) ---
    // Affiliate financials are entered manually (SAM.gov entity_* tables carry no
    // revenue/headcount). The org's own figures live on organization.annual_revenue /
    // organization.employee_count; these hold the linked affiliate's owner-entered figures.

    /// <summary>Affiliate's annual receipts (raw USD), owner-entered. Null = not yet provided (a gap).</summary>
    [Column(TypeName = "decimal(18,2)")]
    public decimal? AffiliateAnnualRevenue { get; set; }

    /// <summary>Affiliate's employee count, owner-entered. Null = not yet provided (a gap).</summary>
    public int? AffiliateEmployeeCount { get; set; }

    /// <summary>'Y' when this JV_PARTNER link is an SBA-approved mentor-protégé agreement (mentor's size excluded from the roll-up).</summary>
    [Required]
    [MaxLength(1)]
    public string MpaApproved { get; set; } = "N";

    /// <summary>Effective date of the approved mentor-protégé agreement (optional).</summary>
    public DateOnly? MpaEffectiveDate { get; set; }

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
