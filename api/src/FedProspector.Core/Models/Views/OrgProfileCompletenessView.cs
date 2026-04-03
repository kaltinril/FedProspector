using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class OrgProfileCompletenessView
{
    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("organization_name")]
    public string? OrganizationName { get; set; }

    [Column("has_uei")]
    public bool HasUei { get; set; }

    [Column("has_cage_code")]
    public bool HasCageCode { get; set; }

    [Column("has_naics")]
    public bool HasNaics { get; set; }

    [Column("has_psc")]
    public bool HasPsc { get; set; }

    [Column("has_certifications")]
    public bool HasCertifications { get; set; }

    [Column("has_past_performance")]
    public bool HasPastPerformance { get; set; }

    [Column("has_address")]
    public bool HasAddress { get; set; }

    [Column("has_business_type")]
    public bool HasBusinessType { get; set; }

    [Column("has_size_standard")]
    public bool HasSizeStandard { get; set; }

    [Column("completeness_pct")]
    public decimal CompletenessPct { get; set; }

    [Column("missing_fields")]
    public string? MissingFields { get; set; }
}
