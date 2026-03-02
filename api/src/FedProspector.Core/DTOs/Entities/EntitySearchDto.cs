namespace FedProspector.Core.DTOs.Entities;

public class EntitySearchDto
{
    public string UeiSam { get; set; } = string.Empty;
    public string LegalBusinessName { get; set; } = string.Empty;
    public string? DbaName { get; set; }
    public string? RegistrationStatus { get; set; }
    public string? PrimaryNaics { get; set; }
    public string? EntityStructureCode { get; set; }
    public string? PopState { get; set; }
    public DateOnly? LastUpdateDate { get; set; }
    public DateOnly? RegistrationExpirationDate { get; set; }
}
