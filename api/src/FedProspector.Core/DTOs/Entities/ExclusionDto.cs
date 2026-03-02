namespace FedProspector.Core.DTOs.Entities;

public class ExclusionDto
{
    public string? ExclusionType { get; set; }
    public string? ExclusionProgram { get; set; }
    public string? ExcludingAgencyName { get; set; }
    public DateOnly? ActivationDate { get; set; }
    public DateOnly? TerminationDate { get; set; }
    public string? AdditionalComments { get; set; }
}
