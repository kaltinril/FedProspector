using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Organizations;

/// <summary>
/// Phase 136 Unit G: a manually-curated "associated" NAICS code an org declares relevant
/// beyond its registered and linked-entity codes.
/// </summary>
public class OrgAssociatedNaicsDto
{
    public int Id { get; set; }

    [Required]
    [MaxLength(11)]
    public string NaicsCode { get; set; } = string.Empty;

    public string? Note { get; set; }

    public DateTime CreatedAt { get; set; }
}

/// <summary>
/// Phase 136 Unit G: request to add an associated NAICS code (with an optional note).
/// </summary>
public class CreateAssociatedNaicsRequest
{
    [Required]
    [MaxLength(11)]
    public string NaicsCode { get; set; } = string.Empty;

    public string? Note { get; set; }
}
