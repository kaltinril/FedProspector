using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("entity_business_type")]
public class EntityBusinessType
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(4)]
    public string BusinessTypeCode { get; set; } = string.Empty;
}
