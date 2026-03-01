using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

/// <summary>
/// Composite primary key (FootnoteId, Section) — requires Fluent API configuration.
/// </summary>
[Table("ref_naics_footnote")]
public class RefNaicsFootnote
{
    [Key]
    [Column("footnote_id", Order = 0)]
    [MaxLength(5)]
    public string FootnoteId { get; set; } = string.Empty;

    [Key]
    [Column("section", Order = 1)]
    [MaxLength(5)]
    public string Section { get; set; } = string.Empty;

    public string Description { get; set; } = string.Empty;
}
