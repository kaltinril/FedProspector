using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("notification")]
public class Notification
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int NotificationId { get; set; }

    [Required]
    public int UserId { get; set; }

    [Required]
    [MaxLength(50)]
    public string NotificationType { get; set; } = string.Empty;

    [Required]
    [MaxLength(200)]
    public string Title { get; set; } = string.Empty;

    public string? Message { get; set; }

    [MaxLength(50)]
    public string? EntityType { get; set; }

    [MaxLength(100)]
    public string? EntityId { get; set; }

    [Required]
    [MaxLength(1)]
    public string IsRead { get; set; } = "N";

    public DateTime? CreatedAt { get; set; }

    public DateTime? ReadAt { get; set; }

    // Navigation property
    [ForeignKey("UserId")]
    public AppUser? User { get; set; }
}
