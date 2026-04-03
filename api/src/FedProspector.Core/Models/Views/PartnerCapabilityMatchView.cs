using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class PartnerCapabilityMatchView
{
    [Column("uei_sam")]
    public string UeiSam { get; set; } = string.Empty;

    [Column("legal_business_name")]
    public string? LegalBusinessName { get; set; }

    [Column("state")]
    public string? State { get; set; }

    [Column("naics_codes")]
    public string? NaicsCodes { get; set; }

    [Column("psc_codes")]
    public string? PscCodes { get; set; }

    [Column("certifications")]
    public string? Certifications { get; set; }

    [Column("agencies_worked_with")]
    public string? AgenciesWorkedWith { get; set; }

    [Column("performance_naics_codes")]
    public string? PerformanceNaicsCodes { get; set; }

    [Column("contract_count")]
    public int ContractCount { get; set; }

    [Column("total_contract_value")]
    public decimal TotalContractValue { get; set; }
}
