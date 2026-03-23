namespace FedProspector.Core.DTOs.Intelligence;

public class DocumentIntelligenceDto
{
    public string NoticeId { get; set; } = "";
    public int AttachmentCount { get; set; }
    public int AnalyzedCount { get; set; }
    public string? LatestExtractionMethod { get; set; }
    public DateTime? LastExtractedAt { get; set; }
    public string? ClearanceRequired { get; set; }
    public string? ClearanceLevel { get; set; }
    public string? ClearanceScope { get; set; }
    public string? EvalMethod { get; set; }
    public string? VehicleType { get; set; }
    public string? IsRecompete { get; set; }
    public string? IncumbentName { get; set; }
    public string? ScopeSummary { get; set; }
    public string? PeriodOfPerformance { get; set; }
    public List<string> LaborCategories { get; set; } = new();
    public List<string> KeyRequirements { get; set; } = new();
    public string OverallConfidence { get; set; } = "low";
    public List<IntelSourceDto> Sources { get; set; } = new();
    public List<AttachmentSummaryDto> Attachments { get; set; } = new();
}

public class IntelSourceDto
{
    public string FieldName { get; set; } = "";
    public string? SourceFilename { get; set; }
    public int? PageNumber { get; set; }
    public string? MatchedText { get; set; }
    public string? SurroundingContext { get; set; }
    public string ExtractionMethod { get; set; } = "";
    public string Confidence { get; set; } = "";
}

public class AttachmentSummaryDto
{
    public int AttachmentId { get; set; }
    public string Filename { get; set; } = "";
    public string? ContentType { get; set; }
    public long? FileSizeBytes { get; set; }
    public int? PageCount { get; set; }
    public string DownloadStatus { get; set; } = "";
    public string ExtractionStatus { get; set; } = "";
    public string? SkipReason { get; set; }
}
