using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("attachment_document")]
public class AttachmentDocument
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int DocumentId { get; set; }

    public int AttachmentId { get; set; }

    [MaxLength(500)]
    public string? Filename { get; set; }

    [MaxLength(100)]
    public string? ContentType { get; set; }

    [Column(TypeName = "longtext")]
    public string? ExtractedText { get; set; }

    public int? PageCount { get; set; }

    public bool IsScanned { get; set; }

    [MaxLength(10)]
    public string? OcrQuality { get; set; }

    [MaxLength(20)]
    public string ExtractionStatus { get; set; } = "pending";

    [MaxLength(64), Column(TypeName = "char(64)")]
    public string? TextHash { get; set; }

    public DateTime? ExtractedAt { get; set; }

    public int ExtractionRetryCount { get; set; }

    public int? LastLoadId { get; set; }

    public DateTime CreatedAt { get; set; }

    // Navigation
    public SamAttachment SamAttachment { get; set; } = null!;
}
