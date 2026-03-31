using FedProspector.Core.DTOs.Admin;
using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/admin")]
[Authorize(Policy = "AdminAccess")]
[EnableRateLimiting("admin")]
public class AdminController : ApiControllerBase
{
    private readonly IAdminService _service;
    private readonly IOrganizationService _orgService;

    public AdminController(IAdminService service, IOrganizationService orgService)
    {
        _service = service;
        _orgService = orgService;
    }

    /// <summary>
    /// Get ETL pipeline status, API usage, and recent errors. System Admin only.
    /// </summary>
    [HttpGet("etl-status")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> GetEtlStatus()
    {
        var result = await _service.GetEtlStatusAsync();
        return Ok(result);
    }

    /// <summary>
    /// Get paginated ETL load history with optional filters. System Admin only.
    /// </summary>
    [HttpGet("load-history")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> GetLoadHistory(
        [FromQuery] string? source = null,
        [FromQuery] string? status = null,
        [FromQuery] int days = 7,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 25)
    {
        var result = await _service.GetLoadHistoryAsync(source, status, days, page, pageSize);
        return Ok(result);
    }

    /// <summary>
    /// Get health check snapshots. System Admin only.
    /// </summary>
    // API-only endpoint — no UI consumer yet (Phase 76-A8)
    [HttpGet("health-snapshots")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> GetHealthSnapshots([FromQuery] int days = 30)
    {
        var result = await _service.GetHealthSnapshotsAsync(days);
        return Ok(result);
    }

    /// <summary>
    /// Get API key usage status from rate limit tracking. System Admin only.
    /// </summary>
    // API-only endpoint — no UI consumer yet (Phase 76-A8)
    [HttpGet("api-keys")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> GetApiKeys()
    {
        var result = await _service.GetApiKeyStatusAsync();
        return Ok(result);
    }

    /// <summary>
    /// Get ETL job definitions with last-run status. System Admin only.
    /// </summary>
    // API-only endpoint — no UI consumer yet (Phase 76-A8)
    [HttpGet("jobs")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> GetJobs()
    {
        var result = await _service.GetJobStatusAsync();
        return Ok(result);
    }

    /// <summary>
    /// Get AI analysis usage summary (cost, tokens, requests). System Admin only.
    /// </summary>
    [HttpGet("ai-usage")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> GetAiUsage([FromQuery] int days = 30)
    {
        var result = await _service.GetAiUsageSummaryAsync(days);
        return Ok(result);
    }

    /// <summary>
    /// List users in the admin's organization. Admin only.
    /// </summary>
    [HttpGet("users")]
    public async Task<IActionResult> GetUsers([FromQuery] int page = 1, [FromQuery] int pageSize = 25)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var users = await _service.GetUsersAsync(orgId.Value, page, pageSize);
        return Ok(users);
    }

    /// <summary>
    /// Update a user's role, admin status, or active status. Admin only.
    /// </summary>
    [HttpPatch("users/{id:int}")]
    public async Task<IActionResult> UpdateUser(int id, [FromBody] UpdateUserRequest request)
    {
        var adminUserId = GetCurrentUserId();
        if (adminUserId == null) return Unauthorized();

        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.UpdateUserAsync(id, request, adminUserId.Value, orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Force-reset a user's password and revoke all sessions. Admin only.
    /// </summary>
    [HttpPost("users/{id:int}/reset-password")]
    public async Task<IActionResult> ResetPassword(int id)
    {
        var adminUserId = GetCurrentUserId();
        if (adminUserId == null) return Unauthorized();

        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.ResetPasswordAsync(id, adminUserId.Value, orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// List all organizations. System Admin only.
    /// </summary>
    [HttpGet("organizations")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> ListOrganizations()
    {
        var result = await _orgService.ListOrganizationsAsync();
        return Ok(result);
    }

    /// <summary>
    /// Create a new organization. System Admin only.
    /// </summary>
    [HttpPost("organizations")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> CreateOrganization([FromBody] CreateOrganizationRequest request)
    {
        try
        {
            var result = await _orgService.CreateOrganizationAsync(request.Name, request.Slug);
            return StatusCode(201, result);
        }
        catch (InvalidOperationException ex)
        {
            return Conflict(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Create the initial owner user for an organization. System Admin only.
    /// </summary>
    [HttpPost("organizations/{id:int}/owner")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> CreateOwner(int id, [FromBody] CreateOwnerRequest request)
    {
        try
        {
            var result = await _orgService.CreateOwnerAsync(id, request.Email, request.Password, request.DisplayName);
            return StatusCode(201, result);
        }
        catch (InvalidOperationException ex)
        {
            return Conflict(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Add a user to any organization. System Admin only.
    /// </summary>
    [HttpPost("organizations/{id:int}/users")]
    [Authorize(Policy = "SystemAdmin")]
    public async Task<IActionResult> CreateUserForOrg(int id, [FromBody] CreateUserRequest request)
    {
        var adminUserId = GetCurrentUserId();
        if (adminUserId == null) return Unauthorized();

        try
        {
            var result = await _orgService.CreateUserAsync(id, request.Email, request.Password, request.DisplayName, request.OrgRole, adminUserId.Value);
            return StatusCode(201, result);
        }
        catch (InvalidOperationException ex)
        {
            return Conflict(new { error = ex.Message });
        }
    }
}
