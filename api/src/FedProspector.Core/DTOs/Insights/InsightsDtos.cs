namespace FedProspector.Core.DTOs.Insights;

public class SimilarOpportunityDto
{
    public string MatchNoticeId { get; set; } = string.Empty;
    public string? MatchTitle { get; set; }
    public string? MatchAgency { get; set; }
    public string? MatchNaics { get; set; }
    public string? MatchSetAside { get; set; }
    public decimal? MatchValue { get; set; }
    public DateTime? MatchPostedDate { get; set; }
    public DateTime? MatchResponseDeadline { get; set; }
    public string? SimilarityFactors { get; set; }
    public int SimilarityScore { get; set; }
}

public class CrossSourceValidationDto
{
    public string CheckId { get; set; } = string.Empty;
    public string CheckName { get; set; } = string.Empty;
    public string SourceAName { get; set; } = string.Empty;
    public long SourceACount { get; set; }
    public string SourceBName { get; set; } = string.Empty;
    public long SourceBCount { get; set; }
    public long Difference { get; set; }
    public decimal PctDifference { get; set; }
    public string Status { get; set; } = string.Empty;
}

public class DataFreshnessDto
{
    public string SourceName { get; set; } = string.Empty;
    public DateTime? LastLoadDate { get; set; }
    public int RecordsLoaded { get; set; }
    public string? LastLoadStatus { get; set; }
    public int? HoursSinceLastLoad { get; set; }
    public string FreshnessStatus { get; set; } = string.Empty;
    public long? TableRowCount { get; set; }
    public string? TableName { get; set; }
}

public class DataCompletenessDto
{
    public string TableName { get; set; } = string.Empty;
    public long TotalRows { get; set; }
    public string FieldName { get; set; } = string.Empty;
    public long NonNullCount { get; set; }
    public long NullCount { get; set; }
    public decimal CompletenessPct { get; set; }
}

public class ProspectCompetitorSummaryDto
{
    public int ProspectId { get; set; }
    public string NoticeId { get; set; } = string.Empty;
    public string? OpportunityTitle { get; set; }
    public string? NaicsCode { get; set; }
    public string? DepartmentName { get; set; }
    public string? SetAsideCode { get; set; }
    public string? LikelyIncumbent { get; set; }
    public string? IncumbentUei { get; set; }
    public decimal? IncumbentContractValue { get; set; }
    public DateOnly? IncumbentContractEnd { get; set; }
    public int EstimatedCompetitorCount { get; set; }
}

public class DataQualityDashboardDto
{
    public List<DataFreshnessDto> Freshness { get; set; } = [];
    public List<DataCompletenessDto> Completeness { get; set; } = [];
    public List<CrossSourceValidationDto> Validation { get; set; } = [];
}
