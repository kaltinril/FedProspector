using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

/// <summary>
/// Composite primary key (PscCode, StartDate) — requires Fluent API configuration.
/// </summary>
[Table("ref_psc_code")]
public class RefPscCode
{
    [Key]
    [Column("psc_code", Order = 0)]
    [MaxLength(10)]
    public string PscCode { get; set; } = string.Empty;

    [Key]
    [Column("start_date", Order = 1)]
    public DateOnly StartDate { get; set; }

    [MaxLength(200)]
    public string? PscName { get; set; }

    public DateOnly? EndDate { get; set; }

    public string? FullDescription { get; set; }

    public string? PscIncludes { get; set; }

    public string? PscExcludes { get; set; }

    public string? PscNotes { get; set; }

    [MaxLength(200)]
    public string? ParentPscCode { get; set; }

    [MaxLength(1)]
    public string? CategoryType { get; set; }

    [Column("level1_category_code")]
    [MaxLength(10)]
    public string? Level1CategoryCode { get; set; }

    [Column("level1_category")]
    [MaxLength(100)]
    public string? Level1Category { get; set; }

    [Column("level2_category_code")]
    [MaxLength(10)]
    public string? Level2CategoryCode { get; set; }

    [Column("level2_category")]
    [MaxLength(100)]
    public string? Level2Category { get; set; }

    public DateTime? CreatedAt { get; set; }
}
