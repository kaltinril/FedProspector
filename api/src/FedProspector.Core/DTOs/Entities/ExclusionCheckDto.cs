namespace FedProspector.Core.DTOs.Entities;

public class ExclusionCheckDto
{
    public string Uei { get; set; } = string.Empty;
    public string? EntityName { get; set; }
    public bool IsExcluded { get; set; }
    public List<ExclusionDto> ActiveExclusions { get; set; } = [];
    public DateTime CheckedAt { get; set; } = DateTime.UtcNow;
}
