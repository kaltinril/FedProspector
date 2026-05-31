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

    /// <summary>
    /// Anonymous liveness probe. Minimal body only — no source-system names,
    /// timestamps, or counts (this endpoint is reachable by unauthenticated callers
    /// on the public internet). Detailed ETL/health snapshots require auth via
    /// AdminController (GET /api/v1/admin/health-snapshots).
    /// </summary>
    [HttpGet]
    [AllowAnonymous]
    public async Task<IActionResult> GetHealth()
    {
        var dbUp = await CheckDatabaseAsync();

        // Always 200 so simple "is it up?" callers keep working; the boolean conveys
        // DB reachability without leaking any internal detail.
        return Ok(new
        {
            status = "ok",
            db = dbUp
        });
    }

    private async Task<bool> CheckDatabaseAsync()
    {
        try
        {
            await _context.Database.ExecuteSqlRawAsync("SELECT 1");
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Health check: database connection failed");
            return false;
        }
    }
}
