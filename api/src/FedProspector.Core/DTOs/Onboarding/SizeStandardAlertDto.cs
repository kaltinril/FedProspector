namespace FedProspector.Core.DTOs.Onboarding;

public class SizeStandardAlertDto
{
    public string NaicsCode { get; set; } = string.Empty;
    public string? SizeStandardType { get; set; }
    public decimal? Threshold { get; set; }
    public decimal? CurrentValue { get; set; }
    public decimal? PctOfThreshold { get; set; }
}
