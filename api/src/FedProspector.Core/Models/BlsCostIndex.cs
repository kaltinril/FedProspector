using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("bls_cost_index")]
public class BlsCostIndex
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(50)]
    [Column("series_id")]
    public string? SeriesId { get; set; }

    [MaxLength(200)]
    [Column("series_name")]
    public string? SeriesName { get; set; }

    [Column("year")]
    public int Year { get; set; }

    [Required]
    [MaxLength(5)]
    [Column("period")]
    public string Period { get; set; } = string.Empty;

    [Column("value", TypeName = "decimal(12,4)")]
    public decimal Value { get; set; }

    [Column("footnotes")]
    public string? Footnotes { get; set; }

    [Column("first_loaded_at")]
    public DateTime? FirstLoadedAt { get; set; }

    [Column("last_loaded_at")]
    public DateTime? LastLoadedAt { get; set; }

    [Column("last_load_id")]
    public int? LastLoadId { get; set; }
}
