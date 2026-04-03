using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class RecompeteCandidateView
{
    [Column("piid")]
    public string Piid { get; set; } = string.Empty;

    [Column("source")]
    public string Source { get; set; } = string.Empty;

    [Column("description")]
    public string? Description { get; set; }

    [Column("naics_code")]
    public string? NaicsCode { get; set; }

    [Column("set_aside_type")]
    public string? SetAsideType { get; set; }

    [Column("vendor_uei")]
    public string? VendorUei { get; set; }

    [Column("vendor_name")]
    public string? VendorName { get; set; }

    [Column("agency_name")]
    public string? AgencyName { get; set; }

    [Column("contracting_office_id")]
    public string? ContractingOfficeId { get; set; }

    [Column("contracting_office_name")]
    public string? ContractingOfficeName { get; set; }

    [Column("contract_value")]
    public decimal? ContractValue { get; set; }

    [Column("dollars_obligated")]
    public decimal? DollarsObligated { get; set; }

    [Column("current_end_date")]
    public DateOnly? CurrentEndDate { get; set; }

    [Column("date_signed")]
    public DateOnly? DateSigned { get; set; }

    [Column("solicitation_number")]
    public string? SolicitationNumber { get; set; }

    [Column("type_of_contract_pricing")]
    public string? TypeOfContractPricing { get; set; }

    [Column("extent_competed")]
    public string? ExtentCompeted { get; set; }

    [Column("days_until_end")]
    public int? DaysUntilEnd { get; set; }

    [Column("incumbent_registration_status")]
    public string? IncumbentRegistrationStatus { get; set; }

    [Column("incumbent_reg_expiration")]
    public DateOnly? IncumbentRegExpiration { get; set; }
}
