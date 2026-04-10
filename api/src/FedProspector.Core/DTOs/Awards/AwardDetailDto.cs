namespace FedProspector.Core.DTOs.Awards;

public class AwardDetailDto
{
    // All FpdsContract fields
    public string ContractId { get; set; } = string.Empty;
    public string? IdvPiid { get; set; }
    public string? AgencyId { get; set; }
    public string? AgencyName { get; set; }
    public string? ContractingOfficeId { get; set; }
    public string? ContractingOfficeName { get; set; }
    public string? FundingAgencyId { get; set; }
    public string? FundingAgencyName { get; set; }
    public string? FundingSubtierCode { get; set; }
    public string? FundingSubtierName { get; set; }
    public string? VendorUei { get; set; }
    public string? VendorName { get; set; }
    public DateOnly? DateSigned { get; set; }
    public DateOnly? EffectiveDate { get; set; }
    public DateOnly? CompletionDate { get; set; }
    public DateOnly? UltimateCompletionDate { get; set; }
    public DateOnly? LastModifiedDate { get; set; }
    public decimal? DollarsObligated { get; set; }
    public decimal? BaseAndAllOptions { get; set; }
    public string? NaicsCode { get; set; }
    public string? NaicsDescription { get; set; }
    public string? PscCode { get; set; }
    public string? PscDescription { get; set; }
    public string? SetAsideType { get; set; }
    public string? SetAsideDescription { get; set; }
    public string? SetAsideCategory { get; set; }
    public string? TypeOfContract { get; set; }
    public string? TypeOfContractPricing { get; set; }
    public string? Description { get; set; }
    public string? PopState { get; set; }
    public string? PopStateName { get; set; }
    public string? PopCountry { get; set; }
    public string? PopCountryName { get; set; }
    public string? PopZip { get; set; }
    public string? ExtentCompeted { get; set; }
    public int? NumberOfOffers { get; set; }
    public string? SolicitationNumber { get; set; }
    public DateOnly? SolicitationDate { get; set; }
    public int? FhOrgId { get; set; }

    // Nested
    public List<TransactionDto> Transactions { get; set; } = [];
    public VendorSummaryDto? VendorProfile { get; set; }
}

public class TransactionDto
{
    public DateOnly ActionDate { get; set; }
    public string? ModificationNumber { get; set; }
    public string? ActionType { get; set; }
    public string? ActionTypeDescription { get; set; }
    public decimal? FederalActionObligation { get; set; }
    public string? Description { get; set; }
}

public class VendorSummaryDto
{
    public string UeiSam { get; set; } = string.Empty;
    public string? LegalBusinessName { get; set; }
    public string? DbaName { get; set; }
    public string? RegistrationStatus { get; set; }
    public string? PrimaryNaics { get; set; }
    public string? EntityUrl { get; set; }
}
