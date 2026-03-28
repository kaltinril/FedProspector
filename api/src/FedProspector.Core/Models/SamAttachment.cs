using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("sam_attachment")]
public class SamAttachment
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int AttachmentId { get; set; }

    [Required, MaxLength(32), Column(TypeName = "char(32)")]
    public string ResourceGuid { get; set; } = string.Empty;

    [Required, MaxLength(500)]
    public string Url { get; set; } = string.Empty;

    [MaxLength(500)]
    public string? Filename { get; set; }

    public long? FileSizeBytes { get; set; }

    [MaxLength(500)]
    public string? FilePath { get; set; }

    [MaxLength(20)]
    public string DownloadStatus { get; set; } = "pending";

    [MaxLength(64), Column(TypeName = "char(64)")]
    public string? ContentHash { get; set; }

    public DateTime? DownloadedAt { get; set; }

    public int DownloadRetryCount { get; set; }

    [MaxLength(100)]
    public string? SkipReason { get; set; }

    public int? LastLoadId { get; set; }

    public DateTime CreatedAt { get; set; }
}
