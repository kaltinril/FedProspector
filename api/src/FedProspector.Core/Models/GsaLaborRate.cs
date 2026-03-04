using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("gsa_labor_rate")]
public class GsaLaborRate
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(200)]
    public string? LaborCategory { get; set; }

    [MaxLength(50)]
    public string? EducationLevel { get; set; }

    public int? MinYearsExperience { get; set; }

    [Column(TypeName = "decimal(10,2)")]
    public decimal? CurrentPrice { get; set; }

    [Column(TypeName = "decimal(10,2)")]
    public decimal? NextYearPrice { get; set; }

    [Column(TypeName = "decimal(10,2)")]
    public decimal? SecondYearPrice { get; set; }

    [MaxLength(200)]
    public string? Schedule { get; set; }

    [MaxLength(200)]
    public string? ContractorName { get; set; }

    [MaxLength(500)]
    public string? Sin { get; set; }

    [MaxLength(10)]
    public string? BusinessSize { get; set; }

    [MaxLength(50)]
    public string? SecurityClearance { get; set; }

    [MaxLength(100)]
    public string? Worksite { get; set; }

    public DateOnly? ContractStart { get; set; }

    public DateOnly? ContractEnd { get; set; }

    [MaxLength(50)]
    public string? IdvPiid { get; set; }

    [MaxLength(200)]
    public string? Category { get; set; }

    [MaxLength(500)]
    public string? Subcategory { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public DateTime? LastLoadedAt { get; set; }

    public int? LastLoadId { get; set; }
}
