using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class PrimeSubRelationshipView
{
    [Column("prime_uei")]
    public string PrimeUei { get; set; } = string.Empty;

    [Column("prime_name")]
    public string? PrimeName { get; set; }

    [Column("sub_uei")]
    public string SubUei { get; set; } = string.Empty;

    [Column("sub_name")]
    public string? SubName { get; set; }

    [Column("subaward_count")]
    public int SubawardCount { get; set; }

    [Column("total_subaward_value")]
    public decimal? TotalSubawardValue { get; set; }

    [Column("avg_subaward_value")]
    public decimal? AvgSubawardValue { get; set; }

    [Column("first_subaward_date")]
    public DateOnly? FirstSubawardDate { get; set; }

    [Column("last_subaward_date")]
    public DateOnly? LastSubawardDate { get; set; }

    [Column("naics_codes_together")]
    public string? NaicsCodesTogether { get; set; }

    [Column("agencies_together")]
    public string? AgenciesTogether { get; set; }
}
