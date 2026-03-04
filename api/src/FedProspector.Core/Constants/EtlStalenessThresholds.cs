namespace FedProspector.Core.Constants;

/// <summary>
/// Shared staleness thresholds (in hours) for each ETL data source.
/// Used by both AdminService and HealthController to ensure consistent freshness verdicts.
/// </summary>
public static class EtlStalenessThresholds
{
    public static readonly Dictionary<string, (string Label, double ThresholdHours)> All = new()
    {
        ["SAM_OPPORTUNITY"] = ("Opportunities", 6),
        ["SAM_ENTITY"] = ("Entity Data", 48),
        ["SAM_FEDHIER"] = ("Federal Hierarchy", 336),
        ["SAM_AWARDS"] = ("Contract Awards", 336),
        ["GSA_CALC"] = ("CALC+ Labor Rates", 1080),
        ["USASPENDING"] = ("USASpending", 1080),
        ["SAM_EXCLUSIONS"] = ("Exclusions", 336),
        ["SAM_SUBAWARD"] = ("Subaward Data", 336),
    };
}
