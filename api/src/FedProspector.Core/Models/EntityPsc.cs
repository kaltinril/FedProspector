using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("entity_psc")]
public class EntityPsc
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(10)]
    public string PscCode { get; set; } = string.Empty;

    // Navigation property
    [ForeignKey("UeiSam")]
    public Entity? Entity { get; set; }
}
