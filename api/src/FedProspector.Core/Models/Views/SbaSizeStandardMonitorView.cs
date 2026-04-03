using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class SbaSizeStandardMonitorView
{
    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("organization_name")]
    public string? OrganizationName { get; set; }

    [Column("naics_code")]
    public string NaicsCode { get; set; } = string.Empty;

    [Column("size_standard_type")]
    public string? SizeStandardType { get; set; }

    [Column("threshold")]
    public decimal? Threshold { get; set; }

    [Column("current_value")]
    public decimal? CurrentValue { get; set; }

    [Column("pct_of_threshold")]
    public decimal? PctOfThreshold { get; set; }
}
