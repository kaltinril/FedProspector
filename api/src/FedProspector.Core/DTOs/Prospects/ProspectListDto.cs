namespace FedProspector.Core.DTOs.Prospects;

public class ProspectListDto
{
    public int ProspectId { get; set; }
    public string NoticeId { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string? Priority { get; set; }
    public decimal? GoNoGoScore { get; set; }
    public decimal? EstimatedValue { get; set; }
    public string? AssignedToName { get; set; }
    public string? CaptureManagerName { get; set; }
    public string? OpportunityTitle { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public string? SetAsideCode { get; set; }
    public string? NaicsCode { get; set; }
    public string? DepartmentName { get; set; }
    public string? Active { get; set; }
    public DateTime? CreatedAt { get; set; }
}
