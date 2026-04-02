using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("labor_category_mapping")]
public class LaborCategoryMapping
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Column("canonical_id")]
    public int? CanonicalId { get; set; }

    [MaxLength(200)]
    [Column("raw_labor_category")]
    public string? RawLaborCategory { get; set; }

    [Column("confidence", TypeName = "decimal(5,2)")]
    public decimal? Confidence { get; set; }

    [MaxLength(20)]
    [Column("match_method")]
    public string? MatchMethod { get; set; }

    [Column("reviewed")]
    public bool Reviewed { get; set; }

    [Column("created_at")]
    public DateTime? CreatedAt { get; set; }
}
