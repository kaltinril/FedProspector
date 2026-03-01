using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

/// <summary>
/// Composite primary key (StateCode, CountryCode) — requires Fluent API configuration.
/// </summary>
[Table("ref_state_code")]
public class RefStateCode
{
    [Key]
    [Column("state_code", Order = 0)]
    [MaxLength(2)]
    public string StateCode { get; set; } = string.Empty;

    [MaxLength(60)]
    public string StateName { get; set; } = string.Empty;

    [Key]
    [Column("country_code", Order = 1)]
    [MaxLength(3)]
    public string CountryCode { get; set; } = "USA";
}
