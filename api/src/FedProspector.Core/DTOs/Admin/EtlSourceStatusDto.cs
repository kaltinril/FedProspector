namespace FedProspector.Core.DTOs.Admin;

public class EtlSourceStatusDto
{
    public string SourceSystem { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public DateTime? LastLoadAt { get; set; }
    public double? HoursSinceLoad { get; set; }
    public double ThresholdHours { get; set; }
    public string Status { get; set; } = string.Empty; // OK, WARNING, STALE, NEVER
    public int RecordsProcessed { get; set; }
}

public class ApiUsageDto
{
    public string SourceSystem { get; set; } = string.Empty;
    public int RequestsMade { get; set; }
    public int MaxRequests { get; set; }
    public int Remaining { get; set; }
    public DateTime? LastRequestAt { get; set; }
}

public class RecentErrorDto
{
    public string SourceSystem { get; set; } = string.Empty;
    public string? LoadType { get; set; }
    public DateTime StartedAt { get; set; }
    public string? ErrorMessage { get; set; }
}
