using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("labor_rate_summary")]
public class LaborRateSummary
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Column("canonical_id")]
    public int CanonicalId { get; set; }

    [MaxLength(100)]
    [Column("category_group")]
    public string? CategoryGroup { get; set; }

    [MaxLength(100)]
    [Column("worksite")]
    public string? Worksite { get; set; }

    [MaxLength(50)]
    [Column("education_level")]
    public string? EducationLevel { get; set; }

    [Column("rate_count")]
    public int RateCount { get; set; }

    [Column("min_rate", TypeName = "decimal(10,2)")]
    public decimal? MinRate { get; set; }

    [Column("avg_rate", TypeName = "decimal(10,2)")]
    public decimal? AvgRate { get; set; }

    [Column("max_rate", TypeName = "decimal(10,2)")]
    public decimal? MaxRate { get; set; }

    [Column("p25_rate", TypeName = "decimal(10,2)")]
    public decimal? P25Rate { get; set; }

    [Column("median_rate", TypeName = "decimal(10,2)")]
    public decimal? MedianRate { get; set; }

    [Column("p75_rate", TypeName = "decimal(10,2)")]
    public decimal? P75Rate { get; set; }

    [Column("refreshed_at")]
    public DateTime? RefreshedAt { get; set; }
}
