namespace FedProspector.Core.DTOs.Admin;

public class LoadHistoryDto
{
    public int LoadId { get; set; }
    public string SourceSystem { get; set; } = string.Empty;
    public string LoadType { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public DateTime StartedAt { get; set; }
    public DateTime? CompletedAt { get; set; }
    public double? DurationSeconds { get; set; }
    public int RecordsRead { get; set; }
    public int RecordsInserted { get; set; }
    public int RecordsUpdated { get; set; }
    public int RecordsErrored { get; set; }
    public string? ErrorMessage { get; set; }
}

public class LoadHistoryResponse
{
    public List<LoadHistoryDto> Items { get; set; } = [];
    public int Page { get; set; }
    public int PageSize { get; set; }
    public int TotalCount { get; set; }
    public int TotalPages { get; set; }
}
