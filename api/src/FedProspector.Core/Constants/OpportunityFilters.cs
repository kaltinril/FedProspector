namespace FedProspector.Core.Constants;

/// <summary>
/// Shared filter constants for opportunity queries.
/// Non-biddable types should be excluded from all list/search endpoints.
/// </summary>
public static class OpportunityFilters
{
    /// <summary>
    /// Notice types that are not biddable and should be excluded from opportunity lists.
    /// Award Notice = already awarded; Justification = J&amp;A sole-source;
    /// Sale of Surplus Property = government selling assets;
    /// Consolidate/(Substantially) Bundle = bundling notification.
    /// </summary>
    public static readonly string[] NonBiddableTypes =
    [
        "Award Notice",
        "Justification",
        "Sale of Surplus Property",
        "Consolidate/(Substantially) Bundle"
    ];
}
