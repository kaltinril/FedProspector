using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("canonical_labor_category")]
public class CanonicalLaborCategory
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Required]
    [MaxLength(200)]
    [Column("canonical_name")]
    public string Name { get; set; } = string.Empty;

    [MaxLength(100)]
    [Column("category_group")]
    public string? CategoryGroup { get; set; }

    [MaxLength(20)]
    [Column("onet_code")]
    public string? OnetCode { get; set; }

    public string? Description { get; set; }

    [Column("created_at")]
    public DateTime? CreatedAt { get; set; }

    [Column("updated_at")]
    public DateTime? UpdatedAt { get; set; }
}
