using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class ProspectCompetitorSummaryView
{
    [Column("prospect_id")]
    public int ProspectId { get; set; }

    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("notice_id")]
    public string NoticeId { get; set; } = string.Empty;

    [Column("opportunity_title")]
    public string? OpportunityTitle { get; set; }

    [Column("naics_code")]
    public string? NaicsCode { get; set; }

    [Column("department_name")]
    public string? DepartmentName { get; set; }

    [Column("set_aside_code")]
    public string? SetAsideCode { get; set; }

    [Column("likely_incumbent")]
    public string? LikelyIncumbent { get; set; }

    [Column("incumbent_uei")]
    public string? IncumbentUei { get; set; }

    [Column("incumbent_contract_value")]
    public decimal? IncumbentContractValue { get; set; }

    [Column("incumbent_contract_end")]
    public DateOnly? IncumbentContractEnd { get; set; }

    [Column("estimated_competitor_count")]
    public int EstimatedCompetitorCount { get; set; }
}
