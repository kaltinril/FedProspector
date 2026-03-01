using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("entity_sba_certification")]
public class EntitySbaCertification
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(10)]
    public string? SbaTypeCode { get; set; }

    [MaxLength(200)]
    public string? SbaTypeDesc { get; set; }

    public DateOnly? CertificationEntryDate { get; set; }

    public DateOnly? CertificationExitDate { get; set; }
}
