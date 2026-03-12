using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("saved_search")]
public class SavedSearch
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int SearchId { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [Required]
    public int UserId { get; set; }

    [Required]
    [MaxLength(100)]
    public string SearchName { get; set; } = string.Empty;

    public string? Description { get; set; }

    [Required]
    [Column(TypeName = "json")]
    public string FilterCriteria { get; set; } = string.Empty;

    [MaxLength(1)]
    public string? NotificationEnabled { get; set; } = "N";

    [MaxLength(1)]
    public string? IsActive { get; set; } = "Y";

    public DateTime? LastRunAt { get; set; }

    public int? LastNewResults { get; set; }

    // Auto-prospect columns (Phase 91-B2)
    [MaxLength(1)]
    public string AutoProspectEnabled { get; set; } = "N";

    [Column(TypeName = "decimal(5,2)")]
    public decimal? MinPwinScore { get; set; } = 30.0m;

    public int? AutoAssignTo { get; set; }

    public DateTime? LastAutoRunAt { get; set; }

    public int? LastAutoCreated { get; set; } = 0;

    public DateTime? CreatedAt { get; set; }

    public DateTime? UpdatedAt { get; set; }

    // Navigation properties
    [ForeignKey("OrganizationId")]
    public Organization? Organization { get; set; }

    [ForeignKey("UserId")]
    public AppUser? User { get; set; }

    [ForeignKey("AutoAssignTo")]
    public AppUser? AutoAssignToUser { get; set; }
}
