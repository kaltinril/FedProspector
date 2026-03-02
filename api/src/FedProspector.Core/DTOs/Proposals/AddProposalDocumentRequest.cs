namespace FedProspector.Core.DTOs.Proposals;

public class AddProposalDocumentRequest
{
    public string FileName { get; set; } = string.Empty;
    public string DocumentType { get; set; } = string.Empty;
    public long? FileSizeBytes { get; set; }
    public string? Notes { get; set; }
}
