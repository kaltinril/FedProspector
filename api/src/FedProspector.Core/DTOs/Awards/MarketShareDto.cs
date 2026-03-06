namespace FedProspector.Core.DTOs.Awards;

public class MarketShareDto
{
    public string VendorName { get; set; } = string.Empty;
    public string VendorUei { get; set; } = string.Empty;
    public int AwardCount { get; set; }
    public decimal TotalValue { get; set; }
    public decimal AverageValue { get; set; }
    public DateTime? LastAwardDate { get; set; }
}
