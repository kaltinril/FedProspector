using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("ref_fips_county")]
public class RefFipsCounty
{
    [Key]
    [MaxLength(5)]
    public string FipsCode { get; set; } = string.Empty;

    [MaxLength(100)]
    public string? CountyName { get; set; }

    [MaxLength(60)]
    public string? StateName { get; set; }
}
