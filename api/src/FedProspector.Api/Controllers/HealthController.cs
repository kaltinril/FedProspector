using FedProspector.Core.Constants;
using FedProspector.Core.DTOs.Health;
using FedProspector.Infrastructure.Data;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.EntityFrameworkCore;

namespace FedProspector.Api.Controllers;

[ApiController]
[Route("health")]
[AllowAnonymous]
[EnableRateLimiting("search")]
public class HealthController : ControllerBase
{
    private readonly FedProspectorDbContext _db;
    private static readonly DateTime StartTime = DateTime.UtcNow;

    // Shared with AdminService — single source of truth in EtlStalenessThresholds.All
    private static readonly Dictionary<string, (string Label, double ThresholdHours)> StalenessThresholds
        = EtlStalenessThresholds.All;

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
                    "SELECT MAX(completed_at) AS Value FROM etl_load_log WHERE status = 'SUCCESS'")
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
                "SELECT source_system, MAX(completed_at) AS last_load FROM etl_load_log WHERE status = 'SUCCESS' GROUP BY source_system")
            .ToListAsync();

        var sources = new List<SourceHealthDto>();
        // Python ETL stores timestamps in local time, so compare with local time
        var now = DateTime.Now;

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
