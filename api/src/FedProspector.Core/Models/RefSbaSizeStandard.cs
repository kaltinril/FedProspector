using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("ref_sba_size_standard")]
public class RefSbaSizeStandard
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(11)]
    public string NaicsCode { get; set; } = string.Empty;

    [MaxLength(500)]
    public string? IndustryDescription { get; set; }

    [Column(TypeName = "decimal(13,2)")]
    public decimal? SizeStandard { get; set; }

    [MaxLength(1)]
    public string? SizeType { get; set; }

    [MaxLength(5)]
    public string? FootnoteId { get; set; }

    public DateOnly? EffectiveDate { get; set; }

    public DateTime? CreatedAt { get; set; }
}
