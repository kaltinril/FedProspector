using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Pipeline;

public class ReverseTimelineRequest
{
    [Required]
    public DateOnly ResponseDeadline { get; set; }

    /// <summary>
    /// Template name (e.g. "standard_rfp") or null if using custom milestones.
    /// </summary>
    [MaxLength(50)]
    public string? TemplateName { get; set; }

    /// <summary>
    /// Custom milestone definitions. If provided, these override the template.
    /// </summary>
    public List<TimelineMilestoneDefinition>? CustomMilestones { get; set; }
}

public class TimelineMilestoneDefinition
{
    [Required]
    [MaxLength(100)]
    public string MilestoneName { get; set; } = string.Empty;

    /// <summary>
    /// Number of days before the deadline for this milestone.
    /// 0 = deadline day itself.
    /// </summary>
    [Required]
    public int DaysBeforeDeadline { get; set; }
}
