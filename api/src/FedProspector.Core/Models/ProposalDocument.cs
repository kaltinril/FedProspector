using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("proposal_document")]
public class ProposalDocument
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int DocumentId { get; set; }

    [Required]
    public int ProposalId { get; set; }

    [Required]
    [MaxLength(50)]
    public string DocumentType { get; set; } = string.Empty;

    [Required]
    [MaxLength(255)]
    public string FileName { get; set; } = string.Empty;

    [Required]
    [MaxLength(500)]
    public string FilePath { get; set; } = string.Empty;

    public long? FileSizeBytes { get; set; }

    public int? UploadedBy { get; set; }

    public DateTime? UploadedAt { get; set; }

    public string? Notes { get; set; }
}
