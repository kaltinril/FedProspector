using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("entity_naics")]
public class EntityNaics
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(11)]
    public string NaicsCode { get; set; } = string.Empty;

    [MaxLength(1)]
    public string? IsPrimary { get; set; }

    [MaxLength(1)]
    public string? SbaSmallBusiness { get; set; }

    [MaxLength(20)]
    public string? NaicsException { get; set; }

    // Navigation property
    [ForeignKey("UeiSam")]
    public Entity? Entity { get; set; }
}
