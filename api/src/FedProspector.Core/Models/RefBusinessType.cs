using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("ref_business_type")]
public class RefBusinessType
{
    [Key]
    [MaxLength(4)]
    public string BusinessTypeCode { get; set; } = string.Empty;

    [MaxLength(200)]
    public string Description { get; set; } = string.Empty;

    [MaxLength(50)]
    public string? Classification { get; set; }

    [MaxLength(50)]
    public string? Category { get; set; }

    [MaxLength(1)]
    public string? IsSocioeconomic { get; set; } = "N";

    [MaxLength(1)]
    public string? IsSmallBusinessRelated { get; set; } = "N";
}
