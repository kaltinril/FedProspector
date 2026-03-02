namespace FedProspector.Core.DTOs.Prospects;

public class ProspectNoteDto
{
    public int NoteId { get; set; }
    public string? NoteType { get; set; }
    public string NoteText { get; set; } = string.Empty;
    public UserSummaryDto? CreatedBy { get; set; }
    public DateTime? CreatedAt { get; set; }
}
