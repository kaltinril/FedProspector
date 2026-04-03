using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("prospect_milestone")]
public class ProspectMilestone
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    [Column("prospect_milestone_id")]
    public int ProspectMilestoneId { get; set; }

    [Required]
    public int ProspectId { get; set; }

    [Required]
    [MaxLength(100)]
    public string MilestoneName { get; set; } = string.Empty;

    [Required]
    public DateOnly TargetDate { get; set; }

    public DateOnly? CompletedDate { get; set; }

    public bool IsCompleted { get; set; }

    public int SortOrder { get; set; }

    public string? Notes { get; set; }

    public DateTime CreatedAt { get; set; }

    public DateTime UpdatedAt { get; set; }

    // Navigation
    [ForeignKey("ProspectId")]
    public Prospect? Prospect { get; set; }
}
