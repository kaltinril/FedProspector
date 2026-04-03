using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class CompetitorDossierView
{
    [Column("uei_sam")]
    public string UeiSam { get; set; } = string.Empty;

    [Column("legal_business_name")]
    public string? LegalBusinessName { get; set; }

    [Column("dba_name")]
    public string? DbaName { get; set; }

    [Column("registration_status")]
    public string? RegistrationStatus { get; set; }

    [Column("registration_expiration_date")]
    public DateOnly? RegistrationExpirationDate { get; set; }

    [Column("primary_naics")]
    public string? PrimaryNaics { get; set; }

    [Column("entity_url")]
    public string? EntityUrl { get; set; }

    [Column("registered_naics_codes")]
    public string? RegisteredNaicsCodes { get; set; }

    [Column("sba_certifications")]
    public string? SbaCertifications { get; set; }

    [Column("business_type_codes")]
    public string? BusinessTypeCodes { get; set; }

    [Column("fpds_contract_count")]
    public int FpdsContractCount { get; set; }

    [Column("fpds_total_obligated")]
    public decimal? FpdsTotalObligated { get; set; }

    [Column("fpds_obligated_3yr")]
    public decimal? FpdsObligated3yr { get; set; }

    [Column("fpds_obligated_5yr")]
    public decimal? FpdsObligated5yr { get; set; }

    [Column("fpds_count_3yr")]
    public int? FpdsCount3yr { get; set; }

    [Column("fpds_count_5yr")]
    public int? FpdsCount5yr { get; set; }

    [Column("fpds_avg_contract_value")]
    public decimal? FpdsAvgContractValue { get; set; }

    [Column("fpds_most_recent_award")]
    public DateOnly? FpdsMostRecentAward { get; set; }

    [Column("fpds_top_naics")]
    public string? FpdsTopNaics { get; set; }

    [Column("fpds_top_agencies")]
    public string? FpdsTopAgencies { get; set; }

    [Column("usa_contract_count")]
    public int UsaContractCount { get; set; }

    [Column("usa_total_obligated")]
    public decimal? UsaTotalObligated { get; set; }

    [Column("usa_obligated_3yr")]
    public decimal? UsaObligated3yr { get; set; }

    [Column("usa_obligated_5yr")]
    public decimal? UsaObligated5yr { get; set; }

    [Column("usa_most_recent_award")]
    public DateOnly? UsaMostRecentAward { get; set; }

    [Column("usa_top_agencies")]
    public string? UsaTopAgencies { get; set; }

    [Column("sub_contract_count")]
    public int SubContractCount { get; set; }

    [Column("sub_total_value")]
    public decimal? SubTotalValue { get; set; }

    [Column("sub_avg_value")]
    public decimal? SubAvgValue { get; set; }

    [Column("prime_sub_awards_count")]
    public int PrimeSubAwardsCount { get; set; }

    [Column("prime_sub_total_value")]
    public decimal? PrimeSubTotalValue { get; set; }
}
