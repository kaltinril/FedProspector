using FedProspector.Core.DTOs.Admin;
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

    /// <summary>
    /// List all users. Admin only.
    /// </summary>
    [HttpGet("users")]
    public async Task<IActionResult> GetUsers()
    {
        var users = await _service.GetUsersAsync();
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

        var result = await _service.UpdateUserAsync(id, request, adminUserId.Value);
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

        var result = await _service.ResetPasswordAsync(id, adminUserId.Value);
        return Ok(result);
    }
}
