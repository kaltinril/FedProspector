namespace FedProspector.Core.DTOs.Admin;

public class ApiKeyStatusDto
{
    public string SourceSystem { get; set; } = string.Empty;
    public int DailyLimit { get; set; }
    public int RequestsMade { get; set; }
    public int Remaining { get; set; }
    public DateTime? LastRequestAt { get; set; }
}
