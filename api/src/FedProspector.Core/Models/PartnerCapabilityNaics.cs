using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

/// <summary>
/// Indexable NAICS dimension for partner_capability_match: one row per
/// (uei_sam, naics_code).  Lets the Teaming Partner Search / Gap Analysis NAICS
/// filter be a single-key indexed join instead of a GROUP_CONCAT substring
/// match.  Populated alongside partner_capability_match by
/// `refresh partner-capability`.
/// </summary>
[Table("partner_capability_naics")]
public class PartnerCapabilityNaics
{
    [Column("uei_sam")]
    public string UeiSam { get; set; } = string.Empty;

    [Column("naics_code")]
    public string NaicsCode { get; set; } = string.Empty;
}
