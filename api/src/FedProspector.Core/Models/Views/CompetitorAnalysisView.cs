namespace FedProspector.Core.Models.Views;

public class CompetitorAnalysisView
{
    public string UeiSam { get; set; } = string.Empty;
    public string? LegalBusinessName { get; set; }
    public string? PrimaryNaics { get; set; }
    public string? NaicsDescription { get; set; }
    public string? NaicsSector { get; set; }
    public string? EntityStructure { get; set; }
    public string? BusinessTypes { get; set; }
    public string? BusinessTypeCategories { get; set; }
    public string? SbaCertifications { get; set; }
    public int PastContracts { get; set; }
    public decimal? TotalObligated { get; set; }
    public DateOnly? MostRecentAward { get; set; }
}
