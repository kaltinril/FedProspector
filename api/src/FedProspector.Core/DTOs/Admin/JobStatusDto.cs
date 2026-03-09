namespace FedProspector.Core.DTOs.Admin;

public class JobStatusDto
{
    public string SourceSystem { get; set; } = string.Empty;
    public string LoadType { get; set; } = string.Empty;
    public DateTime? LastRunAt { get; set; }
    public string? LastStatus { get; set; }
    public double? LastDurationSeconds { get; set; }
    public int RecordsProcessed { get; set; }
    public int RunCount { get; set; }
}
