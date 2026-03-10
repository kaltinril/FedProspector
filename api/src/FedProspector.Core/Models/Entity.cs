using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("entity")]
public class Entity
{
    [Key]
    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(9)]
    public string? UeiDuns { get; set; }

    [MaxLength(5)]
    public string? CageCode { get; set; }

    [MaxLength(9)]
    public string? Dodaac { get; set; }

    [MaxLength(1)]
    public string? RegistrationStatus { get; set; }

    [MaxLength(2)]
    public string? PurposeOfRegistration { get; set; }

    public DateOnly? InitialRegistrationDate { get; set; }

    public DateOnly? RegistrationExpirationDate { get; set; }

    public DateOnly? LastUpdateDate { get; set; }

    public DateOnly? ActivationDate { get; set; }

    [MaxLength(120)]
    public string LegalBusinessName { get; set; } = string.Empty;

    [MaxLength(120)]
    public string? DbaName { get; set; }

    [MaxLength(60)]
    public string? EntityDivision { get; set; }

    [MaxLength(10)]
    public string? EntityDivisionNumber { get; set; }

    [MaxLength(1)]
    public string? DnbOpenDataFlag { get; set; }

    public DateOnly? EntityStartDate { get; set; }

    [MaxLength(4)]
    public string? FiscalYearEndClose { get; set; }

    [MaxLength(200)]
    public string? EntityUrl { get; set; }

    [MaxLength(2)]
    public string? EntityStructureCode { get; set; }

    [MaxLength(2)]
    public string? EntityTypeCode { get; set; }

    [MaxLength(2)]
    public string? ProfitStructureCode { get; set; }

    [MaxLength(2)]
    public string? OrganizationStructureCode { get; set; }

    [MaxLength(2)]
    public string? StateOfIncorporation { get; set; }

    [MaxLength(3)]
    public string? CountryOfIncorporation { get; set; }

    [MaxLength(6)]
    public string? PrimaryNaics { get; set; }

    [MaxLength(1)]
    public string? CreditCardUsage { get; set; }

    [MaxLength(1)]
    public string? CorrespondenceFlag { get; set; }

    [MaxLength(1)]
    public string? DebtSubjectToOffset { get; set; }

    [MaxLength(1)]
    public string? ExclusionStatusFlag { get; set; }

    [MaxLength(4)]
    public string? NoPublicDisplayFlag { get; set; }

    [MaxLength(10)]
    public string? EvsSource { get; set; }

    [Column("eft_indicator")]
    [MaxLength(10)]
    public string? EftIndicator { get; set; }

    [MaxLength(64)]
    public string? RecordHash { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public DateTime? LastLoadedAt { get; set; }

    public int? LastLoadId { get; set; }
}
