namespace FedProspector.Core.DTOs.Health;

public class SourceLoadResult
{
    public string SourceSystem { get; set; } = string.Empty;
    public DateTime? LastLoad { get; set; }
}
