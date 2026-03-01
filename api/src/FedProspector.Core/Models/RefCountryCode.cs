using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("ref_country_code")]
public class RefCountryCode
{
    [MaxLength(100)]
    public string CountryName { get; set; } = string.Empty;

    [MaxLength(2)]
    public string TwoCode { get; set; } = string.Empty;

    [Key]
    [MaxLength(3)]
    public string ThreeCode { get; set; } = string.Empty;

    [MaxLength(4)]
    public string? NumericCode { get; set; }

    [MaxLength(3)]
    public string? Independent { get; set; }

    [MaxLength(1)]
    public string? IsIsoStandard { get; set; } = "Y";

    [MaxLength(1)]
    public string? SamGovRecognized { get; set; } = "Y";

    public DateTime? CreatedAt { get; set; }
}
