namespace FedProspector.Core.Interfaces;

/// <summary>
/// Per-IP failed-login throttle for the public (unauthenticated) login surface.
/// Counts only failed login attempts; blocks an IP after too many failures within
/// a sliding window. Separate from the per-account lockout in <see cref="IAuthService"/>.
/// </summary>
public interface ILoginThrottleService
{
    /// <summary>
    /// Returns true if the given client IP is currently blocked from attempting login.
    /// </summary>
    bool IsBlocked(string? ipAddress);

    /// <summary>
    /// Record a failed login attempt for the given client IP. Once the failure count
    /// crosses the threshold within the sliding window, the IP becomes blocked.
    /// </summary>
    void RecordFailure(string? ipAddress);

    /// <summary>
    /// Clear all failure tracking and any block for the given client IP.
    /// Called on a successful login.
    /// </summary>
    void Clear(string? ipAddress);
}
