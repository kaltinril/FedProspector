using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Pipeline;

public class UpdateMilestoneRequest
{
    [MaxLength(100)]
    public string? MilestoneName { get; set; }

    public DateOnly? TargetDate { get; set; }

    public DateOnly? CompletedDate { get; set; }

    public bool? IsCompleted { get; set; }

    public int? SortOrder { get; set; }

    public string? Notes { get; set; }
}
