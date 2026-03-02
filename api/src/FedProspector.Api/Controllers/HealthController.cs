using FedProspector.Infrastructure.Data;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace FedProspector.Api.Controllers;

[ApiController]
[Route("health")]
[AllowAnonymous]
public class HealthController : ControllerBase
{
    private readonly FedProspectorDbContext _db;
    private static readonly DateTime StartTime = DateTime.UtcNow;

    // Same staleness thresholds as AdminService
    private static readonly Dictionary<string, (string Label, double ThresholdHours)> StalenessThresholds = new()
    {
        ["SAM_OPPORTUNITY_KEY2"] = ("Opportunities", 6),
        ["SAM_ENTITY"] = ("Entity Data", 48),
        ["SAM_FEDHIER"] = ("Federal Hierarchy", 336),
        ["SAM_AWARDS"] = ("Contract Awards", 336),
        ["GSA_CALC"] = ("CALC+ Labor Rates", 1080),
        ["USASPENDING"] = ("USASpending", 1080),
        ["SAM_EXCLUSIONS"] = ("Exclusions", 336),
        ["SAM_SUBAWARD"] = ("Subaward Data", 336),
    };

    public HealthController(FedProspectorDbContext db)
    {
        _db = db;
    }

    [HttpGet]
    public async Task<IActionResult> GetHealth()
    {
        var result = new HealthResponse
        {
            Uptime = (DateTime.UtcNow - StartTime).ToString(@"d\.hh\:mm\:ss")
        };

        // Check MySQL connectivity
        try
        {
            await _db.Database.ExecuteSqlRawAsync("SELECT 1");
            result.Database = "connected";
        }
        catch (Exception)
        {
            result.Database = "disconnected";
            result.Status = "unhealthy";
        }

        // Check ETL data freshness
        try
        {
            var lastLoad = await _db.Database
                .SqlQueryRaw<DateTime?>(
                    "SELECT MAX(completed_at) AS Value FROM etl_load_log WHERE status = 'success'")
                .FirstOrDefaultAsync();

            result.LastEtlLoad = lastLoad?.ToString("o");
        }
        catch (Exception)
        {
            result.LastEtlLoad = "unknown";
        }

        // Per-source freshness check
        if (result.Database == "connected")
        {
            try
            {
                result.Sources = await GetSourceHealthAsync();

                // If any source is stale and DB is still up, mark as degraded
                if (result.Status == "healthy" && result.Sources.Any(s => s.Status == "stale"))
                {
                    result.Status = "degraded";
                }
            }
            catch (Exception)
            {
                // Source checks are best-effort; don't fail the health endpoint
            }
        }

        return result.Status == "healthy" ? Ok(result) : StatusCode(503, result);
    }

    private async Task<List<SourceHealthDto>> GetSourceHealthAsync()
    {
        var latestLoads = await _db.Database
            .SqlQueryRaw<SourceLoadResult>(
                "SELECT source_system AS SourceSystem, MAX(completed_at) AS LastLoad FROM etl_load_log WHERE status = 'SUCCESS' GROUP BY source_system")
            .ToListAsync();

        var sources = new List<SourceHealthDto>();
        var now = DateTime.UtcNow;

        foreach (var (key, (label, threshold)) in StalenessThresholds)
        {
            var load = latestLoads.FirstOrDefault(l => l.SourceSystem == key);
            double? hoursSince = load?.LastLoad != null
                ? (now - load.LastLoad.Value).TotalHours
                : null;

            string status;
            if (load?.LastLoad == null)
                status = "unknown";
            else if (hoursSince > threshold)
                status = "stale";
            else if (hoursSince > threshold * 0.8)
                status = "warning";
            else
                status = "healthy";

            sources.Add(new SourceHealthDto
            {
                Name = label,
                Status = status,
                LastLoad = load?.LastLoad
            });
        }

        return sources;
    }
}

public class SourceLoadResult
{
    public string SourceSystem { get; set; } = string.Empty;
    public DateTime? LastLoad { get; set; }
}

public class HealthResponse
{
    public string Status { get; set; } = "healthy";
    public string Database { get; set; } = "unknown";
    public string? LastEtlLoad { get; set; }
    public string Uptime { get; set; } = string.Empty;
    public List<SourceHealthDto>? Sources { get; set; }
}

public class SourceHealthDto
{
    public string Name { get; set; } = string.Empty;
    public string Status { get; set; } = "unknown";
    public DateTime? LastLoad { get; set; }
}
