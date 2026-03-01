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

    public DateTime? CreatedAt { get; set; }

    public DateTime? UpdatedAt { get; set; }
}
