namespace FedProspector.Core.Services;

/// <summary>
/// Canonical normalization for federal identifiers (solicitation numbers, PIIDs).
/// Phase 132: government APIs send the same identifier in mixed formats — some with
/// dashes, some without. The canonical form used for matching/cross-reference is
/// <c>trim → uppercase → remove dashes</c>.
///
/// This rule MUST be identical across SQL, Python, and C#:
/// <list type="bullet">
///   <item>SQL: <c>UPPER(REPLACE(TRIM(solicitation_number), '-', ''))</c></item>
///   <item>Python: <c>value.strip().upper().replace("-", "")</c></item>
///   <item>C#: <c>value.Trim().ToUpperInvariant().Replace("-", "")</c></item>
/// </list>
///
/// The original identifier is preserved for display; the normalized form is for
/// matching only and should never be shown to users.
/// </summary>
public static class IdentifierNormalizer
{
    /// <summary>
    /// Returns the dashless, uppercased, trimmed canonical form of a federal
    /// identifier. Returns null for null input and an empty string for whitespace-only
    /// input (mirroring trim semantics).
    /// </summary>
    public static string? Normalize(string? value)
    {
        if (value is null) return null;
        return value.Trim().ToUpperInvariant().Replace("-", "");
    }
}
