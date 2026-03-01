using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("ref_entity_structure")]
public class RefEntityStructure
{
    [Key]
    [MaxLength(2)]
    public string StructureCode { get; set; } = string.Empty;

    [MaxLength(200)]
    public string Description { get; set; } = string.Empty;
}
