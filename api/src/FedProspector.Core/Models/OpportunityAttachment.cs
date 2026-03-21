using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("opportunity_attachment")]
public class OpportunityAttachment
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int AttachmentId { get; set; }

    [MaxLength(100)]
    public string NoticeId { get; set; } = string.Empty;

    [MaxLength(2000)]
    public string? Url { get; set; }

    [MaxLength(500)]
    public string? Filename { get; set; }

    [MaxLength(100)]
    public string? ContentType { get; set; }

    public long? FileSizeBytes { get; set; }

    [MaxLength(500)]
    public string? FilePath { get; set; }

    [Column(TypeName = "longtext")]
    public string? ExtractedText { get; set; }

    public int? PageCount { get; set; }

    public bool? IsScanned { get; set; }

    [MaxLength(20)]
    public string? OcrQuality { get; set; }

    [MaxLength(20)]
    public string DownloadStatus { get; set; } = "pending";

    [MaxLength(20)]
    public string ExtractionStatus { get; set; } = "pending";

    [MaxLength(64)]
    public string? ContentHash { get; set; }

    [MaxLength(64)]
    public string? TextHash { get; set; }

    public DateTime? DownloadedAt { get; set; }

    public DateTime? ExtractedAt { get; set; }

    public int? LastLoadId { get; set; }

    public DateTime? CreatedAt { get; set; }
}
