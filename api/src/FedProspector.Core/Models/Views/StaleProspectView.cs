using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class StaleProspectView
{
    [Column("prospect_id")]
    public int ProspectId { get; set; }

    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("notice_id")]
    public string NoticeId { get; set; } = string.Empty;

    [Column("opportunity_title")]
    public string? OpportunityTitle { get; set; }

    [Column("status")]
    public string Status { get; set; } = string.Empty;

    [Column("priority")]
    public string? Priority { get; set; }

    [Column("days_since_update")]
    public int DaysSinceUpdate { get; set; }

    [Column("assigned_to")]
    public int? AssignedTo { get; set; }

    [Column("assigned_to_name")]
    public string? AssignedToName { get; set; }

    [Column("estimated_value")]
    public decimal? EstimatedValue { get; set; }

    [Column("last_updated_at")]
    public DateTime LastUpdatedAt { get; set; }
}
