using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Pipeline;

public class BulkStatusUpdateRequest
{
    [Required]
    [MinLength(1)]
    public List<int> ProspectIds { get; set; } = new();

    [Required]
    [MaxLength(30)]
    public string NewStatus { get; set; } = string.Empty;

    public string? Notes { get; set; }
}
