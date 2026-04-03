using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class TeamingNetworkView
{
    [Column("vendor_uei")]
    public string VendorUei { get; set; } = string.Empty;

    [Column("vendor_name")]
    public string? VendorName { get; set; }

    [Column("relationship_direction")]
    public string RelationshipDirection { get; set; } = string.Empty;

    [Column("partner_uei")]
    public string PartnerUei { get; set; } = string.Empty;

    [Column("partner_name")]
    public string? PartnerName { get; set; }

    [Column("award_count")]
    public int AwardCount { get; set; }

    [Column("total_value")]
    public decimal? TotalValue { get; set; }
}
