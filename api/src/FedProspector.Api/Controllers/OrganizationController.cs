using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/org")]
[Authorize]
[EnableRateLimiting("write")]
public class OrganizationController : ApiControllerBase
{
    private readonly IOrganizationService _service;

    public OrganizationController(IOrganizationService service) => _service = service;

    /// <summary>
    /// Get the current user's organization details.
    /// </summary>
    [HttpGet]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetOrganization()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetOrganizationAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Update the current user's organization name. Requires OrgAdmin role.
    /// </summary>
    [HttpPatch]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> UpdateOrganization([FromBody] UpdateOrganizationRequest request)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.UpdateOrganizationAsync(orgId.Value, request.Name);
        return Ok(result);
    }

    /// <summary>
    /// List members of the current user's organization.
    /// </summary>
    [HttpGet("members")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetMembers()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetMembersAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Create an invite for the current user's organization. Requires OrgAdmin role.
    /// </summary>
    [HttpPost("invites")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> CreateInvite([FromBody] CreateInviteRequest request)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var userId = GetCurrentUserId();
        if (userId is null) return Unauthorized();

        var result = await _service.CreateInviteAsync(orgId.Value, request.Email, request.OrgRole, userId.Value);
        return StatusCode(201, result);
    }

    /// <summary>
    /// List pending invites for the current user's organization. Requires OrgAdmin role.
    /// </summary>
    [HttpGet("invites")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetPendingInvites()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetPendingInvitesAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Revoke a pending invite. Requires OrgAdmin role.
    /// </summary>
    [HttpDelete("invites/{id:int}")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> RevokeInvite(int id)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        await _service.RevokeInviteAsync(orgId.Value, id);
        return NoContent();
    }

}
