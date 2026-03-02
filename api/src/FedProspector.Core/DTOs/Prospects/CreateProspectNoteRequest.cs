namespace FedProspector.Core.DTOs.Prospects;

public class CreateProspectNoteRequest
{
    public string NoteType { get; set; } = string.Empty;
    public string NoteText { get; set; } = string.Empty;
}
