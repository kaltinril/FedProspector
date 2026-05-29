namespace FedProspector.Core.Models;

/// <summary>
/// Result of an on-demand SAM.gov description fetch.
///
/// Three terminal outcomes:
///   1. Success — DescriptionText is populated, Success=true.
///   2. NotFound — the opportunity (or its description URL) does not exist.
///   3. Error — non-rate-limit failure; ErrorMessage describes it.
///
/// One non-terminal outcome:
///   4. Queued — SAM.gov returned HTTP 429 and the request has been
///      enqueued as a DataLoadRequest for the Python poller to retry.
///      QueuedMessage carries a user-friendly explanation. Success=false.
/// </summary>
public record FetchDescriptionResult(
    string? DescriptionText,
    string? ErrorMessage,
    bool Success,
    bool NotFound = false,
    bool Queued = false,
    string? QueuedMessage = null);
