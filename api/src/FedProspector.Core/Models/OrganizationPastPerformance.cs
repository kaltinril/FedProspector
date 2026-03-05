using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("organization_past_performance")]
public class OrganizationPastPerformance
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [MaxLength(50)]
    public string? ContractNumber { get; set; }

    [MaxLength(200)]
    public string? AgencyName { get; set; }

    [Column(TypeName = "text")]
    public string? Description { get; set; }

    [MaxLength(11)]
    public string? NaicsCode { get; set; }

    [Column(TypeName = "decimal(18,2)")]
    public decimal? ContractValue { get; set; }

    public DateTime? PeriodStart { get; set; }

    public DateTime? PeriodEnd { get; set; }

    [Required]
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    // Navigation properties
    public Organization Organization { get; set; } = null!;
}
