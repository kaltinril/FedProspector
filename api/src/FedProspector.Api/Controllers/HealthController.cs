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
            result.Status = "degraded";
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

        return result.Status == "healthy" ? Ok(result) : StatusCode(503, result);
    }
}

public class HealthResponse
{
    public string Status { get; set; } = "healthy";
    public string Database { get; set; } = "unknown";
    public string? LastEtlLoad { get; set; }
    public string Uptime { get; set; } = string.Empty;
}
