namespace FedProspector.Core.DTOs.Opportunities;

public class ResourceLinkDto
{
    public string Url { get; set; } = string.Empty;
    public string? Filename { get; set; }
    public string? ContentType { get; set; }
    public long? FileSizeBytes { get; set; }
    public string? DownloadStatus { get; set; }
    public string? SkipReason { get; set; }
}
