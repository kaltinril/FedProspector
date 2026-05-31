using FedProspector.Core.Interfaces;
using Microsoft.Extensions.Caching.Memory;

namespace FedProspector.Infrastructure.Services;

/// <summary>
/// IMemoryCache-backed per-IP failed-login throttle.
///
/// Threat model: only UNAUTHENTICATED attackers. This guards the login endpoint
/// against credential stuffing from a single source IP. Deployment is a direct
/// port-forward with NO reverse proxy, so HttpContext.Connection.RemoteIpAddress is
/// the real client IP (do NOT add ForwardedHeaders).
///
/// Separate from the per-account lockout in AuthService and from the global
/// RateLimiter middleware (which is intentionally disabled).
/// </summary>
public class LoginThrottleService : ILoginThrottleService
{
    /// <summary>Failures from one IP within <see cref="FailureWindow"/> that trip a block.</summary>
    public const int MaxFailuresPerWindow = 10;

    /// <summary>Sliding window over which failures are counted.</summary>
    public static readonly TimeSpan FailureWindow = TimeSpan.FromMinutes(15);

    /// <summary>How long an IP stays blocked once it trips the threshold.</summary>
    public static readonly TimeSpan BlockDuration = TimeSpan.FromMinutes(15);

    private readonly IMemoryCache _cache;
    private readonly object _lock = new();

    public LoginThrottleService(IMemoryCache cache)
    {
        _cache = cache;
    }

    public bool IsBlocked(string? ipAddress)
    {
        if (string.IsNullOrEmpty(ipAddress)) return false;
        return _cache.TryGetValue(BlockKey(ipAddress), out _);
    }

    public void RecordFailure(string? ipAddress)
    {
        if (string.IsNullOrEmpty(ipAddress)) return;

        lock (_lock)
        {
            var now = DateTime.UtcNow;
            var cutoff = now - FailureWindow;

            var failures = _cache.Get<List<DateTime>>(FailuresKey(ipAddress)) ?? new List<DateTime>();
            failures.RemoveAll(t => t <= cutoff);
            failures.Add(now);

            // Keep the failure list alive for the length of the sliding window.
            _cache.Set(FailuresKey(ipAddress), failures, FailureWindow);

            if (failures.Count >= MaxFailuresPerWindow)
            {
                _cache.Set(BlockKey(ipAddress), now, BlockDuration);
            }
        }
    }

    public void Clear(string? ipAddress)
    {
        if (string.IsNullOrEmpty(ipAddress)) return;

        lock (_lock)
        {
            _cache.Remove(FailuresKey(ipAddress));
            _cache.Remove(BlockKey(ipAddress));
        }
    }

    private static string FailuresKey(string ip) => $"login_throttle:failures:{ip}";
    private static string BlockKey(string ip) => $"login_throttle:blocked:{ip}";
}
