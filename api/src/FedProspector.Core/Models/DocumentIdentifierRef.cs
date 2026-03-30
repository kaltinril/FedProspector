using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("document_identifier_ref")]
public class DocumentIdentifierRef
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int RefId { get; set; }

    public int DocumentId { get; set; }

    [MaxLength(30)]
    public string IdentifierType { get; set; } = string.Empty;

    [MaxLength(200)]
    public string IdentifierValue { get; set; } = string.Empty;

    [MaxLength(500)]
    public string? RawText { get; set; }

    [Column(TypeName = "text")]
    public string? Context { get; set; }

    public int? CharOffsetStart { get; set; }

    public int? CharOffsetEnd { get; set; }

    [MaxLength(10)]
    public string? Confidence { get; set; }

    [MaxLength(50)]
    public string? MatchedTable { get; set; }

    [MaxLength(50)]
    public string? MatchedColumn { get; set; }

    [MaxLength(200)]
    public string? MatchedId { get; set; }

    public int? LastLoadId { get; set; }

    public DateTime? CreatedAt { get; set; }
}
