using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("opportunity_intel_source")]
public class OpportunityIntelSource
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int SourceId { get; set; }

    public int IntelId { get; set; }

    [MaxLength(50)]
    public string FieldName { get; set; } = string.Empty;

    public int? AttachmentId { get; set; }

    [MaxLength(500)]
    public string? SourceFilename { get; set; }

    public int? PageNumber { get; set; }

    public int? CharOffsetStart { get; set; }

    public int? CharOffsetEnd { get; set; }

    [MaxLength(500)]
    public string? MatchedText { get; set; }

    [Column(TypeName = "text")]
    public string? SurroundingContext { get; set; }

    [MaxLength(100)]
    public string? PatternName { get; set; }

    [MaxLength(20)]
    public string? ExtractionMethod { get; set; }

    [MaxLength(10)]
    public string? Confidence { get; set; }

    public DateTime? CreatedAt { get; set; }
}
