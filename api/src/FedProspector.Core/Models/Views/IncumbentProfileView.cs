namespace FedProspector.Core.Models.Views;

public class IncumbentProfileView
{
    public string UeiSam { get; set; } = string.Empty;
    public string? LegalBusinessName { get; set; }
    public string? DbaName { get; set; }
    public string? RegistrationStatus { get; set; }
    public string? PrimaryNaics { get; set; }
    public string? EntityUrl { get; set; }
    public string? SbaCertifications { get; set; }
    public int TotalPastContracts { get; set; }
    public decimal? TotalObligated { get; set; }
    public DateOnly? MostRecentAward { get; set; }
}
