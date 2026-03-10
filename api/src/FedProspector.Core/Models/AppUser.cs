using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("app_user")]
public class AppUser
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int UserId { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(50)]
    public string Username { get; set; } = string.Empty;

    [Required]
    [MaxLength(100)]
    public string DisplayName { get; set; } = string.Empty;

    [MaxLength(200)]
    public string? Email { get; set; }

    [MaxLength(255)]
    public string? PasswordHash { get; set; }

    [MaxLength(20)]
    public string? Role { get; set; } = "USER";

    public DateTime? LastLoginAt { get; set; }

    [MaxLength(1)]
    public string? IsActive { get; set; } = "Y";

    [Required]
    [MaxLength(1)]
    public string IsOrgAdmin { get; set; } = "N";

    [Required]
    public bool IsSystemAdmin { get; set; } = false;

    [Required]
    [MaxLength(1)]
    public string MfaEnabled { get; set; } = "N";

    [Required]
    [MaxLength(50)]
    public string OrgRole { get; set; } = "member";

    public int? InvitedBy { get; set; }

    public DateTime? InviteAcceptedAt { get; set; }

    [Required]
    [MaxLength(1)]
    public string ForcePasswordChange { get; set; } = "N";

    [Required]
    public int FailedLoginAttempts { get; set; } = 0;

    public DateTime? LockedUntil { get; set; }

    public DateTime? CreatedAt { get; set; }

    public DateTime? UpdatedAt { get; set; }

    // Navigation properties
    [ForeignKey("OrganizationId")]
    public Organization? Organization { get; set; }

    [ForeignKey("InvitedBy")]
    public AppUser? InvitedByUser { get; set; }
}
