using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("activity_log")]
public class ActivityLog
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public long ActivityId { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    public int? UserId { get; set; }

    [Required]
    [MaxLength(50)]
    public string Action { get; set; } = string.Empty;

    [Required]
    [MaxLength(50)]
    public string EntityType { get; set; } = string.Empty;

    [MaxLength(100)]
    public string? EntityId { get; set; }

    [Column(TypeName = "json")]
    public string? Details { get; set; }

    [MaxLength(45)]
    public string? IpAddress { get; set; }

    public DateTime? CreatedAt { get; set; }

    // Navigation properties
    [ForeignKey("OrganizationId")]
    public Organization? Organization { get; set; }

    [ForeignKey("UserId")]
    public AppUser? User { get; set; }
}
