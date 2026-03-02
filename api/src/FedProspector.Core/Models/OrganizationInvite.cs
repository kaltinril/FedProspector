using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("organization_invite")]
public class OrganizationInvite
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int InviteId { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(255)]
    public string Email { get; set; } = string.Empty;

    [Required]
    [MaxLength(64)]
    public string InviteCode { get; set; } = string.Empty;

    [Required]
    [MaxLength(50)]
    public string OrgRole { get; set; } = "member";

    [Required]
    public int InvitedBy { get; set; }

    [Required]
    public DateTime ExpiresAt { get; set; }

    public DateTime? AcceptedAt { get; set; }

    [Required]
    public DateTime CreatedAt { get; set; }

    // Navigation properties
    [ForeignKey("OrganizationId")]
    public Organization? Organization { get; set; }

    [ForeignKey("InvitedBy")]
    public AppUser? InvitedByUser { get; set; }
}
