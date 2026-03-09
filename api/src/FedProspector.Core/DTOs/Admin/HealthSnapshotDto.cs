namespace FedProspector.Core.DTOs.Admin;

public class HealthSnapshotDto
{
    public int SnapshotId { get; set; }
    public DateTime CheckedAt { get; set; }
    public string OverallStatus { get; set; } = string.Empty;
    public int AlertCount { get; set; }
    public int ErrorCount { get; set; }
    public int StaleSourceCount { get; set; }
    public string? Details { get; set; }
}
