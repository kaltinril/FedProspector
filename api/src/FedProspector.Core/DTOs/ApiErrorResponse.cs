namespace FedProspector.Core.DTOs;

public class ApiErrorResponse
{
    public int StatusCode { get; set; }
    public string Message { get; set; } = string.Empty;
    public string? Detail { get; set; }
    public IDictionary<string, string[]>? Errors { get; set; }
    public string TraceId { get; set; } = string.Empty;
}
