using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

/// <summary>
/// Phase 136 Unit G: a manually-curated "associated" NAICS code that an organization
/// declares relevant BEYOND its registered (organization_naics) and linked-entity codes.
/// EF-Core-owned app table. No FK to organization (project convention — organization_id
/// references the org logically). Deduped via a unique key on (organization_id, naics_code).
/// </summary>
[Table("organization_associated_naics")]
public class OrganizationAssociatedNaics
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(11)]
    public string NaicsCode { get; set; } = string.Empty;

    /// <summary>Optional free-text note explaining why this code is relevant.</summary>
    public string? Note { get; set; }

    [Required]
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
