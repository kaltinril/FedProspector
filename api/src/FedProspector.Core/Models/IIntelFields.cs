namespace FedProspector.Core.Models;

/// <summary>
/// Common intel fields shared between per-document intel summaries
/// and per-opportunity rollup summaries. Used by aggregation helpers
/// in AttachmentIntelService to work with either record type.
/// </summary>
public interface IIntelFields
{
    string ExtractionMethod { get; }
    string? ClearanceRequired { get; }
    string? ClearanceLevel { get; }
    string? ClearanceScope { get; }
    string? ClearanceDetails { get; }
    string? EvalMethod { get; }
    string? EvalDetails { get; }
    string? VehicleType { get; }
    string? VehicleDetails { get; }
    string? IsRecompete { get; }
    string? IncumbentName { get; }
    string? RecompeteDetails { get; }
    string? PricingStructure { get; }
    string? PlaceOfPerformance { get; }
    string? ScopeSummary { get; }
    string? PeriodOfPerformance { get; }
    string? LaborCategories { get; }
    string? KeyRequirements { get; }
    string OverallConfidence { get; }
    string? ConfidenceDetails { get; }
    DateTime? ExtractedAt { get; }
}
