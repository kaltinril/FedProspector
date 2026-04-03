using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class CrossSourceValidationView
{
    [Column("check_id")]
    public string CheckId { get; set; } = string.Empty;

    [Column("check_name")]
    public string CheckName { get; set; } = string.Empty;

    [Column("source_a_name")]
    public string SourceAName { get; set; } = string.Empty;

    [Column("source_a_count")]
    public long SourceACount { get; set; }

    [Column("source_b_name")]
    public string SourceBName { get; set; } = string.Empty;

    [Column("source_b_count")]
    public long SourceBCount { get; set; }

    [Column("difference")]
    public long Difference { get; set; }

    [Column("pct_difference")]
    public decimal PctDifference { get; set; }

    [Column("status")]
    public string Status { get; set; } = string.Empty;
}
