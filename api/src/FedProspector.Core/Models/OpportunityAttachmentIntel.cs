using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("opportunity_attachment_intel")]
public class OpportunityAttachmentIntel
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int IntelId { get; set; }

    [MaxLength(100)]
    public string NoticeId { get; set; } = string.Empty;

    public int? AttachmentId { get; set; }

    [MaxLength(20)]
    public string? ExtractionMethod { get; set; }

    [MaxLength(64)]
    public string? SourceTextHash { get; set; }

    [MaxLength(1)]
    public string? ClearanceRequired { get; set; }

    [MaxLength(50)]
    public string? ClearanceLevel { get; set; }

    [MaxLength(100)]
    public string? ClearanceScope { get; set; }

    [Column(TypeName = "text")]
    public string? ClearanceDetails { get; set; }

    [MaxLength(100)]
    public string? EvalMethod { get; set; }

    [Column(TypeName = "text")]
    public string? EvalDetails { get; set; }

    [MaxLength(100)]
    public string? VehicleType { get; set; }

    [Column(TypeName = "text")]
    public string? VehicleDetails { get; set; }

    [MaxLength(1)]
    public string? IsRecompete { get; set; }

    [MaxLength(200)]
    public string? IncumbentName { get; set; }

    [Column(TypeName = "text")]
    public string? RecompeteDetails { get; set; }

    [Column(TypeName = "text")]
    public string? ScopeSummary { get; set; }

    [MaxLength(200)]
    public string? PeriodOfPerformance { get; set; }

    [Column(TypeName = "json")]
    public string? LaborCategories { get; set; }

    [Column(TypeName = "json")]
    public string? KeyRequirements { get; set; }

    [MaxLength(10)]
    public string? OverallConfidence { get; set; }

    [Column(TypeName = "json")]
    public string? ConfidenceDetails { get; set; }

    public int? LastLoadId { get; set; }

    public DateTime? ExtractedAt { get; set; }
}
