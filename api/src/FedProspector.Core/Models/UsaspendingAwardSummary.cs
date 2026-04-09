using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("usaspending_award_summary")]
public class UsaspendingAwardSummary
{
    [Column("naics_code")]
    public string NaicsCode { get; set; } = "";

    [Column("agency_cgac")]
    [MaxLength(10)]
    public string AgencyCgac { get; set; } = "";

    [Column("agency_name")]
    public string AgencyName { get; set; } = "";

    [Column("vendor_count")]
    public int VendorCount { get; set; }

    [Column("contract_count")]
    public int ContractCount { get; set; }

    [Column("total_value")]
    public decimal TotalValue { get; set; }

    [Column("computed_at")]
    public DateTime ComputedAt { get; set; }
}
