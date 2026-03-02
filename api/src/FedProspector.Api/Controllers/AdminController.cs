using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace FedProspector.Api.Controllers;

[Route("api/v1/admin")]
[Authorize(Roles = "admin")]
public class AdminController : ApiControllerBase
{
    private readonly IAdminService _service;

    public AdminController(IAdminService service)
    {
        _service = service;
    }

    /// <summary>
    /// Get ETL pipeline status, API usage, and recent errors. Admin only.
    /// </summary>
    [HttpGet("etl-status")]
    public async Task<IActionResult> GetEtlStatus()
    {
        var result = await _service.GetEtlStatusAsync();
        return Ok(result);
    }
}
