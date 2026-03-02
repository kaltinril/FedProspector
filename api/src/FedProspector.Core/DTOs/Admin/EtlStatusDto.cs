namespace FedProspector.Core.DTOs.Admin;

public class EtlStatusDto
{
    public List<EtlSourceStatusDto> Sources { get; set; } = [];
    public List<ApiUsageDto> ApiUsage { get; set; } = [];
    public List<RecentErrorDto> RecentErrors { get; set; } = [];
    public List<string> Alerts { get; set; } = [];
}
