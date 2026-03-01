using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("ref_sba_type")]
public class RefSbaType
{
    [Key]
    [MaxLength(10)]
    public string SbaTypeCode { get; set; } = string.Empty;

    [MaxLength(200)]
    public string Description { get; set; } = string.Empty;

    [MaxLength(100)]
    public string? ProgramName { get; set; }
}
