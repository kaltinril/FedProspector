using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Pipeline;

public class CreateMilestoneRequest
{
    [Required]
    [MaxLength(100)]
    public string MilestoneName { get; set; } = string.Empty;

    [Required]
    public DateOnly TargetDate { get; set; }

    public int SortOrder { get; set; }

    public string? Notes { get; set; }
}
