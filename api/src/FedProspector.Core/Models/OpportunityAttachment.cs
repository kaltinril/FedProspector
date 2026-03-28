using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

/// <summary>
/// Many-to-many mapping between opportunities and SAM attachments.
/// Composite PK (NoticeId, AttachmentId) configured in OnModelCreating.
/// </summary>
[Table("opportunity_attachment")]
public class OpportunityAttachment
{
    [MaxLength(100)]
    public string NoticeId { get; set; } = string.Empty;

    public int AttachmentId { get; set; }

    [Required, MaxLength(500)]
    public string Url { get; set; } = string.Empty;

    public int? LastLoadId { get; set; }

    public DateTime CreatedAt { get; set; }

    // Navigation
    public SamAttachment SamAttachment { get; set; } = null!;
}
