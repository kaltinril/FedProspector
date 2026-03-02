namespace FedProspector.Core.DTOs.Proposals;

public class ProposalDocumentDto
{
    public int DocumentId { get; set; }
    public string DocumentType { get; set; } = string.Empty;
    public string FileName { get; set; } = string.Empty;
    public long? FileSizeBytes { get; set; }
    public int? UploadedBy { get; set; }
    public DateTime? UploadedAt { get; set; }
    public string? Notes { get; set; }
}
