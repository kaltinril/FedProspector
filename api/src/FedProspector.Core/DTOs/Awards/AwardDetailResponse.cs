namespace FedProspector.Core.DTOs.Awards;

public class AwardDetailResponse
{
    public string ContractId { get; set; } = string.Empty;
    public string DataStatus { get; set; } = "not_loaded"; // "full", "partial", "not_loaded"
    public bool HasFpdsData { get; set; }
    public bool HasUsaspendingData { get; set; }
    public AwardDetailDto? Detail { get; set; }
    public LoadRequestStatusDto? LoadStatus { get; set; }
}

public class LoadRequestStatusDto
{
    public int? RequestId { get; set; }
    public string? RequestType { get; set; }
    public string? Status { get; set; }
    public DateTime? RequestedAt { get; set; }
    public string? ErrorMessage { get; set; }
    public string? ResultSummary { get; set; }
}

public class RequestLoadDto
{
    public string Tier { get; set; } = "usaspending"; // "usaspending" or "fpds"
}
