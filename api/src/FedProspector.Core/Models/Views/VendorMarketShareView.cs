using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class VendorMarketShareView
{
    [Column("naics_code")]
    public string NaicsCode { get; set; } = string.Empty;

    [Column("vendor_name")]
    public string VendorName { get; set; } = string.Empty;

    [Column("vendor_uei")]
    public string VendorUei { get; set; } = string.Empty;

    [Column("award_count")]
    public int AwardCount { get; set; }

    [Column("total_value")]
    public decimal? TotalValue { get; set; }

    [Column("average_value")]
    public decimal? AverageValue { get; set; }

    [Column("last_award_date")]
    public DateTime? LastAwardDate { get; set; }
}
