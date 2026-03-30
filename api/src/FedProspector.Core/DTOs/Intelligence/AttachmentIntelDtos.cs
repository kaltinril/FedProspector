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
    public string? PricingStructure { get; set; }
    public string? PlaceOfPerformance { get; set; }
    public List<string> LaborCategories { get; set; } = new();
    public List<string> KeyRequirements { get; set; } = new();
    public string OverallConfidence { get; set; } = "low";
    public List<string> AvailableMethods { get; set; } = new();
    public Dictionary<string, string>? ConfidenceDetails { get; set; }
    public string? ClearanceDetails { get; set; }
    public string? EvalDetails { get; set; }
    public string? VehicleDetails { get; set; }
    public string? RecompeteDetails { get; set; }
    public string? PricingDetails { get; set; }
    public string? PopDetails { get; set; }
    public List<IntelSourceDto> Sources { get; set; } = new();
    public List<AttachmentSummaryDto> Attachments { get; set; } = new();
    public List<MergedSourcePassageDto> MergedPassages { get; set; } = new();
    public List<AttachmentIntelBreakdownDto>? PerAttachmentIntel { get; set; }
}

public class IntelSourceDto
{
    public string FieldName { get; set; } = "";
    public string? SourceFilename { get; set; }
    public int? PageNumber { get; set; }
    public string? MatchedText { get; set; }
    public string? SurroundingContext { get; set; }
    public string ExtractionMethod { get; set; } = "";
    public int? CharOffsetStart { get; set; }
    public int? CharOffsetEnd { get; set; }
    public string Confidence { get; set; } = "";
}

public class AnalysisEstimateDto
{
    public string NoticeId { get; set; } = string.Empty;
    public int AttachmentCount { get; set; }
    public int TotalChars { get; set; }
    public int EstimatedInputTokens { get; set; }
    public int EstimatedOutputTokens { get; set; }
    public decimal EstimatedCostUsd { get; set; }
    public string Model { get; set; } = "haiku";
    public int AlreadyAnalyzed { get; set; }
    public int RemainingToAnalyze { get; set; }
}

public class AttachmentSummaryDto
{
    public int AttachmentId { get; set; }
    public string? ResourceGuid { get; set; }
    public string Filename { get; set; } = "";
    public string? Url { get; set; }
    public string? ContentType { get; set; }
    public long? FileSizeBytes { get; set; }
    public int? PageCount { get; set; }
    public string DownloadStatus { get; set; } = "";
    public string ExtractionStatus { get; set; } = "";
    public string? SkipReason { get; set; }
}

public class AttachmentIntelBreakdownDto
{
    public int AttachmentId { get; set; }
    public string Filename { get; set; } = "";
    public string ExtractionMethod { get; set; } = "";
    public string? Confidence { get; set; }
    public string? ClearanceRequired { get; set; }
    public string? ClearanceLevel { get; set; }
    public string? EvalMethod { get; set; }
    public string? VehicleType { get; set; }
    public string? IsRecompete { get; set; }
    public string? IncumbentName { get; set; }
    public string? PricingStructure { get; set; }
    public string? PlaceOfPerformance { get; set; }
}

public class MergedSourcePassageDto
{
    public string FieldName { get; set; } = "";
    public string Filename { get; set; } = "";
    public int? PageNumber { get; set; }
    public List<string> Methods { get; set; } = new();
    public List<string> Confidences { get; set; } = new();
    public string Text { get; set; } = "";
    public List<HighlightSpan> Highlights { get; set; } = new();
    public int MatchCount { get; set; }
}

public class HighlightSpan
{
    public int Start { get; set; }
    public int End { get; set; }
    public string MatchedText { get; set; } = "";
}

public class IdentifierRefDto
{
    public string IdentifierType { get; set; } = "";
    public string IdentifierValue { get; set; } = "";
    public string? RawText { get; set; }
    public string Confidence { get; set; } = "medium";
    public string? MatchedTable { get; set; }
    public string? MatchedColumn { get; set; }
    public string? MatchedId { get; set; }
    public int MentionCount { get; set; }
}

public class PredecessorCandidateDto
{
    public string NoticeId { get; set; } = "";
    public string PredecessorPiid { get; set; } = "";
    public string? PredecessorVendorName { get; set; }
    public string? PredecessorVendorUei { get; set; }
    public decimal? PredecessorAwardAmount { get; set; }
    public string? PredecessorSetAsideType { get; set; }
    public string? PredecessorNaics { get; set; }
    public string Confidence { get; set; } = "medium";
    public int DocumentMentions { get; set; }
}

public class OpportunityIdentifiersDto
{
    public string NoticeId { get; set; } = "";
    public List<IdentifierRefDto> Identifiers { get; set; } = new();
    public List<PredecessorCandidateDto> PredecessorCandidates { get; set; } = new();
}
