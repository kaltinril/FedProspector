using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("ref_set_aside_type")]
public class RefSetAsideType
{
    [Key]
    [MaxLength(10)]
    public string SetAsideCode { get; set; } = string.Empty;

    [MaxLength(200)]
    public string Description { get; set; } = string.Empty;

    [MaxLength(1)]
    public string? IsSmallBusiness { get; set; } = "Y";

    [MaxLength(50)]
    public string? Category { get; set; }
}
