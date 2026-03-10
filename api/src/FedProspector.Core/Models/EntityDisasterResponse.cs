using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("entity_disaster_response")]
public class EntityDisasterResponse
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(10)]
    public string? StateCode { get; set; }

    [MaxLength(60)]
    public string? StateName { get; set; }

    [MaxLength(5)]
    public string? CountyCode { get; set; }

    [MaxLength(100)]
    public string? CountyName { get; set; }

    [MaxLength(10)]
    public string? MsaCode { get; set; }

    [MaxLength(100)]
    public string? MsaName { get; set; }

    // Navigation property
    [ForeignKey("UeiSam")]
    public Entity? Entity { get; set; }
}
