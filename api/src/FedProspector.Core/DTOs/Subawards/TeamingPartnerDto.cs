namespace FedProspector.Core.DTOs.Subawards;

public class TeamingPartnerDto
{
    public string? PrimeUei { get; set; }
    public string? PrimeName { get; set; }
    public int SubCount { get; set; }
    public decimal? TotalSubAmount { get; set; }
    public int UniqueSubs { get; set; }
    public string? NaicsCodes { get; set; }
}
