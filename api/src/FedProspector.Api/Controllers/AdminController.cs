using FedProspector.Core.DTOs.Admin;
using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/admin")]
[Authorize(Roles = "admin")]
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
    /// Get ETL pipeline status, API usage, and recent errors. Admin only.
    /// </summary>
    [HttpGet("etl-status")]
    public async Task<IActionResult> GetEtlStatus()
    {
        var isSystemAdmin = User.HasClaim("is_system_admin", "true");
        if (!isSystemAdmin)
            return Forbid();

        var result = await _service.GetEtlStatusAsync();
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
    /// Create a new organization. System Admin only.
    /// </summary>
    [HttpPost("organizations")]
    public async Task<IActionResult> CreateOrganization([FromBody] CreateOrganizationRequest request)
    {
        var isSystemAdmin = User.HasClaim("is_system_admin", "true");
        if (!isSystemAdmin)
            return Forbid();

        var result = await _orgService.CreateOrganizationAsync(request.Name, request.Slug);
        return StatusCode(201, result);
    }

    /// <summary>
    /// Create the initial owner user for an organization. System Admin only.
    /// </summary>
    [HttpPost("organizations/{id:int}/owner")]
    public async Task<IActionResult> CreateOwner(int id, [FromBody] CreateOwnerRequest request)
    {
        var isSystemAdmin = User.HasClaim("is_system_admin", "true");
        if (!isSystemAdmin)
            return Forbid();

        var result = await _orgService.CreateOwnerAsync(id, request.Email, request.Password, request.DisplayName);
        return StatusCode(201, result);
    }
}
