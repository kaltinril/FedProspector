using FedProspector.Infrastructure.Data;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace FedProspector.Api.Controllers;

[Route("health")]
[ApiController]
public class HealthController : ControllerBase
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<HealthController> _logger;

    public HealthController(FedProspectorDbContext context, ILogger<HealthController> logger)
    {
        _context = context;
        _logger = logger;
    }

    [HttpGet]
    [AllowAnonymous]
    public async Task<IActionResult> GetHealth()
    {
        var dbStatus = await CheckDatabaseAsync();
        var etlStatus = await CheckEtlFreshnessAsync();

        var overallStatus = (dbStatus.Status, etlStatus.Status) switch
        {
            ("Healthy", "Healthy") => "Healthy",
            _ when dbStatus.Status == "Unhealthy" => "Unhealthy",
            _ => "Degraded"
        };

        return Ok(new
        {
            status = overallStatus,
            database = dbStatus,
            etlFreshness = etlStatus
        });
    }

    private async Task<HealthComponent> CheckDatabaseAsync()
    {
        try
        {
            await _context.Database.ExecuteSqlRawAsync("SELECT 1");
            return new HealthComponent
            {
                Status = "Healthy",
                Description = "Database connection successful"
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Health check: database connection failed");
            return new HealthComponent
            {
                Status = "Unhealthy",
                Description = "Database connection failed"
            };
        }
    }

    private async Task<HealthComponent> CheckEtlFreshnessAsync()
    {
        try
        {
            await _context.Database.OpenConnectionAsync();
            try
            {
                var connection = _context.Database.GetDbConnection();
                await using var cmd = connection.CreateCommand();
                cmd.CommandText =
                    "SELECT source_system, MAX(completed_at) AS last_load, COUNT(*) AS total_loads " +
                    "FROM etl_load_log WHERE status = 'SUCCESS' GROUP BY source_system ORDER BY source_system";

                var sources = new List<(string Source, DateTime? LastLoad, int TotalLoads)>();
                await using var reader = await cmd.ExecuteReaderAsync();
                while (await reader.ReadAsync())
                {
                    sources.Add((
                        reader.GetString(0),
                        reader.IsDBNull(1) ? null : reader.GetDateTime(1),
                        reader.GetInt32(2)
                    ));
                }

                if (sources.Count == 0)
                {
                    return new HealthComponent
                    {
                        Status = "Degraded",
                        Description = "No successful ETL loads found"
                    };
                }

                var now = DateTime.UtcNow;
                var staleCount = sources.Count(s => s.LastLoad.HasValue && (now - s.LastLoad.Value).TotalHours > 168);
                var status = staleCount == 0 ? "Healthy" : staleCount < sources.Count ? "Degraded" : "Unhealthy";

                var data = new Dictionary<string, object?>();
                foreach (var (source, lastLoad, totalLoads) in sources)
                {
                    var age = lastLoad.HasValue ? now - lastLoad.Value : (TimeSpan?)null;
                    data[$"{source}_lastLoad"] = lastLoad?.ToString("yyyy-MM-dd HH:mm") ?? "never";
                    data[$"{source}_age"] = FormatAge(age);
                    data[$"{source}_totalLoads"] = totalLoads.ToString();
                }

                var mostRecent = sources.Where(s => s.LastLoad.HasValue).Max(s => s.LastLoad!.Value);
                var mostRecentAge = now - mostRecent;

                return new HealthComponent
                {
                    Status = status,
                    Description = $"{sources.Count} data sources — most recent load {FormatAge(mostRecentAge)} ago",
                    Data = data
                };
            }
            finally
            {
                await _context.Database.CloseConnectionAsync();
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Health check: could not check ETL freshness");
            return new HealthComponent
            {
                Status = "Degraded",
                Description = "Could not check ETL freshness"
            };
        }
    }

    private static string FormatAge(TimeSpan? age)
    {
        if (age == null) return "never";
        if (age.Value.TotalHours < 1) return $"{age.Value.TotalMinutes:F0}m";
        if (age.Value.TotalHours < 48) return $"{age.Value.TotalHours:F0}h";
        return $"{age.Value.TotalDays:F0}d";
    }

    private sealed class HealthComponent
    {
        public required string Status { get; init; }
        public string? Description { get; init; }
        public Dictionary<string, object?>? Data { get; init; }
    }
}
