namespace FedProspector.Core.DTOs.Intelligence;

public class RecompeteCandidateDto
{
    public string Piid { get; set; } = string.Empty;
    public string Source { get; set; } = string.Empty;
    public string? Description { get; set; }
    public string? NaicsCode { get; set; }
    public string? SetAsideType { get; set; }
    public string? VendorUei { get; set; }
    public string? VendorName { get; set; }
    public string? AgencyName { get; set; }
    public string? ContractingOfficeId { get; set; }
    public string? ContractingOfficeName { get; set; }
    public decimal? ContractValue { get; set; }
    public decimal? DollarsObligated { get; set; }
    public DateOnly? CurrentEndDate { get; set; }
    public DateOnly? DateSigned { get; set; }
    public string? SolicitationNumber { get; set; }
    public string? TypeOfContractPricing { get; set; }
    public string? ExtentCompeted { get; set; }
    public int? DaysUntilEnd { get; set; }
    public string? IncumbentRegistrationStatus { get; set; }
    public DateOnly? IncumbentRegExpiration { get; set; }
}

public class AgencyRecompetePatternDto
{
    public string ContractingOfficeId { get; set; } = string.Empty;
    public string? ContractingOfficeName { get; set; }
    public string? AgencyName { get; set; }
    public decimal? IncumbentRetentionRatePct { get; set; }
    public decimal? NewVendorPenetrationPct { get; set; }
    public decimal? SetAsideShiftFrequencyPct { get; set; }
    public decimal? AvgSolicitationLeadTimeDays { get; set; }
    public decimal? BridgeExtensionFrequencyPct { get; set; }
    public decimal? SoleSourceRatePct { get; set; }
    public decimal? NaicsShiftRatePct { get; set; }
    public int TotalContractsAnalyzed { get; set; }
}

public class CompetitorDossierDto
{
    public string UeiSam { get; set; } = string.Empty;
    public string? LegalBusinessName { get; set; }
    public string? DbaName { get; set; }
    public string? RegistrationStatus { get; set; }
    public DateOnly? RegistrationExpirationDate { get; set; }
    public string? PrimaryNaics { get; set; }
    public string? EntityUrl { get; set; }
    public string? RegisteredNaicsCodes { get; set; }
    public string? SbaCertifications { get; set; }
    public string? BusinessTypeCodes { get; set; }
    // FPDS metrics
    public int FpdsContractCount { get; set; }
    public decimal? FpdsTotalObligated { get; set; }
    public decimal? FpdsObligated3yr { get; set; }
    public decimal? FpdsObligated5yr { get; set; }
    public int? FpdsCount3yr { get; set; }
    public int? FpdsCount5yr { get; set; }
    public decimal? FpdsAvgContractValue { get; set; }
    public DateOnly? FpdsMostRecentAward { get; set; }
    public string? FpdsTopNaics { get; set; }
    public string? FpdsTopAgencies { get; set; }
    // USASpending metrics
    public int UsaContractCount { get; set; }
    public decimal? UsaTotalObligated { get; set; }
    public decimal? UsaObligated3yr { get; set; }
    public decimal? UsaObligated5yr { get; set; }
    public DateOnly? UsaMostRecentAward { get; set; }
    public string? UsaTopAgencies { get; set; }
    // Subcontracting
    public int SubContractCount { get; set; }
    public decimal? SubTotalValue { get; set; }
    public decimal? SubAvgValue { get; set; }
    public int PrimeSubAwardsCount { get; set; }
    public decimal? PrimeSubTotalValue { get; set; }
}

public class AgencyBuyingPatternDto
{
    public string AgencyId { get; set; } = string.Empty;
    public string? AgencyName { get; set; }
    public int AwardYear { get; set; }
    public int AwardQuarter { get; set; }
    public int ContractCount { get; set; }
    public decimal? TotalObligated { get; set; }
    // Set-aside percentages
    public decimal? SmallBusinessPct { get; set; }
    public decimal? WosbPct { get; set; }
    public decimal? EightAPct { get; set; }
    public decimal? HubzonePct { get; set; }
    public decimal? SdvosbPct { get; set; }
    public decimal? UnrestrictedPct { get; set; }
    // Competition percentages
    public decimal? FullCompetitionPct { get; set; }
    public decimal? SoleSourcePct { get; set; }
    public decimal? LimitedCompetitionPct { get; set; }
    // Contract type percentages
    public decimal? FfpPct { get; set; }
    public decimal? TmPct { get; set; }
    public decimal? CostPlusPct { get; set; }
    public decimal? OtherTypePct { get; set; }
}

public class ContractingOfficeProfileDto
{
    public string ContractingOfficeId { get; set; } = string.Empty;
    public string? ContractingOfficeName { get; set; }
    public string? AgencyName { get; set; }
    public int TotalAwards { get; set; }
    public decimal? TotalObligated { get; set; }
    public decimal? AvgAwardValue { get; set; }
    public DateOnly? EarliestAward { get; set; }
    public DateOnly? LatestAward { get; set; }
    public string? TopNaicsCodes { get; set; }
    // Set-aside preferences
    public decimal? SmallBusinessPct { get; set; }
    public decimal? WosbPct { get; set; }
    public decimal? EightAPct { get; set; }
    public decimal? HubzonePct { get; set; }
    public decimal? SdvosbPct { get; set; }
    public decimal? UnrestrictedPct { get; set; }
    // Contract type distribution
    public decimal? FfpPct { get; set; }
    public decimal? TmPct { get; set; }
    public decimal? CostPlusPct { get; set; }
    // Competition preference
    public decimal? FullCompetitionPct { get; set; }
    public decimal? SoleSourcePct { get; set; }
    public decimal? AvgProcurementDays { get; set; }
}
