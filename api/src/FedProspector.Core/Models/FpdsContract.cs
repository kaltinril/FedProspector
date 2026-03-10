using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

/// <summary>
/// Composite primary key (ContractId, ModificationNumber) — requires Fluent API configuration.
/// </summary>
[Table("fpds_contract")]
public class FpdsContract
{
    [Key]
    [Column("contract_id", Order = 0)]
    [MaxLength(50)]
    public string ContractId { get; set; } = string.Empty;

    [Key]
    [Column("modification_number", Order = 1)]
    [MaxLength(10)]
    public string ModificationNumber { get; set; } = "0";

    [MaxLength(50)]
    public string? IdvPiid { get; set; }

    [MaxLength(10)]
    public string? TransactionNumber { get; set; }

    [MaxLength(10)]
    public string? AgencyId { get; set; }

    [MaxLength(200)]
    public string? AgencyName { get; set; }

    [MaxLength(20)]
    public string? ContractingOfficeId { get; set; }

    [MaxLength(200)]
    public string? ContractingOfficeName { get; set; }

    [MaxLength(10)]
    public string? FundingAgencyId { get; set; }

    [MaxLength(200)]
    public string? FundingAgencyName { get; set; }

    [Column("funding_subtier_code")]
    [MaxLength(20)]
    public string? FundingSubtierCode { get; set; }

    [Column("funding_subtier_name")]
    [MaxLength(200)]
    public string? FundingSubtierName { get; set; }

    [MaxLength(12)]
    public string? VendorUei { get; set; }

    [MaxLength(200)]
    public string? VendorName { get; set; }

    [MaxLength(9)]
    public string? VendorDuns { get; set; }

    public DateOnly? DateSigned { get; set; }

    public DateOnly? EffectiveDate { get; set; }

    public DateOnly? CompletionDate { get; set; }

    public DateOnly? LastModifiedDate { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? DollarsObligated { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? BaseAndAllOptions { get; set; }

    [MaxLength(6)]
    public string? NaicsCode { get; set; }

    [MaxLength(10)]
    public string? PscCode { get; set; }

    [MaxLength(20)]
    public string? SetAsideType { get; set; }

    [MaxLength(10)]
    public string? TypeOfContract { get; set; }

    public string? Description { get; set; }

    [MaxLength(6)]
    public string? PopState { get; set; }

    [MaxLength(3)]
    public string? PopCountry { get; set; }

    [MaxLength(10)]
    public string? PopZip { get; set; }

    [MaxLength(10)]
    public string? ExtentCompeted { get; set; }

    public int? NumberOfOffers { get; set; }

    [Column("far1102_exception_code")]
    [MaxLength(2)]
    public string? Far1102ExceptionCode { get; set; }

    [Column("far1102_exception_name")]
    [MaxLength(100)]
    public string? Far1102ExceptionName { get; set; }

    [MaxLength(100)]
    public string? ReasonForModification { get; set; }

    [MaxLength(100)]
    public string? SolicitationNumber { get; set; }

    public DateOnly? SolicitationDate { get; set; }

    public DateOnly? UltimateCompletionDate { get; set; }

    [MaxLength(10)]
    public string? TypeOfContractPricing { get; set; }

    [MaxLength(50)]
    public string? CoBusSizeDetermination { get; set; }

    [MaxLength(64)]
    public string? RecordHash { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public DateTime? LastLoadedAt { get; set; }

    public int? LastLoadId { get; set; }
}
