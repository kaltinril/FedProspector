using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("usaspending_award")]
public class UsaspendingAward
{
    [Key]
    [MaxLength(100)]
    public string GeneratedUniqueAwardId { get; set; } = string.Empty;

    [MaxLength(50)]
    public string? Piid { get; set; }

    [MaxLength(30)]
    public string? Fain { get; set; }

    [MaxLength(70)]
    public string? Uri { get; set; }

    [MaxLength(50)]
    public string? AwardType { get; set; }

    public string? AwardDescription { get; set; }

    [MaxLength(200)]
    public string? RecipientName { get; set; }

    [MaxLength(12)]
    public string? RecipientUei { get; set; }

    [MaxLength(200)]
    public string? RecipientParentName { get; set; }

    [MaxLength(12)]
    public string? RecipientParentUei { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? TotalObligation { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? BaseAndAllOptionsValue { get; set; }

    public DateOnly? StartDate { get; set; }

    public DateOnly? EndDate { get; set; }

    public DateOnly? LastModifiedDate { get; set; }

    [MaxLength(200)]
    public string? AwardingAgencyName { get; set; }

    [MaxLength(200)]
    public string? AwardingSubAgencyName { get; set; }

    [MaxLength(200)]
    public string? FundingAgencyName { get; set; }

    [MaxLength(6)]
    public string? NaicsCode { get; set; }

    [MaxLength(500)]
    public string? NaicsDescription { get; set; }

    [MaxLength(10)]
    public string? PscCode { get; set; }

    [MaxLength(50)]
    public string? TypeOfSetAside { get; set; }

    [MaxLength(200)]
    public string? TypeOfSetAsideDescription { get; set; }

    [MaxLength(6)]
    public string? PopState { get; set; }

    [MaxLength(3)]
    public string? PopCountry { get; set; }

    [MaxLength(10)]
    public string? PopZip { get; set; }

    [MaxLength(100)]
    public string? PopCity { get; set; }

    [MaxLength(50)]
    public string? SolicitationIdentifier { get; set; }

    public short? FiscalYear { get; set; }

    public DateTime? FpdsEnrichedAt { get; set; }

    [MaxLength(64)]
    public string? RecordHash { get; set; }

    public int? LastLoadId { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public DateTime? LastLoadedAt { get; set; }

    /// <summary>
    /// Navigation to SAM entity via RecipientUei (no DB-level FK constraint).
    /// </summary>
    public Entity? RecipientEntity { get; set; }
}
