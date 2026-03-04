namespace FedProspector.Core.DTOs.Health;

public class HealthResponse
{
    public string Status { get; set; } = "healthy";
    public string Database { get; set; } = "unknown";
    public string? LastEtlLoad { get; set; }
    public string Uptime { get; set; } = string.Empty;
    public List<SourceHealthDto>? Sources { get; set; }
}

public class SourceHealthDto
{
    public string Name { get; set; } = string.Empty;
    public string Status { get; set; } = "unknown";
    public DateTime? LastLoad { get; set; }
}
