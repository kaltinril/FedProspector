using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/prospects")]
[Authorize]
[EnableRateLimiting("write")]
public class ProspectsController : ApiControllerBase
{
    private readonly IProspectService _service;

    public ProspectsController(IProspectService service) => _service = service;

    /// <summary>
    /// Create a new prospect from an opportunity.
    /// </summary>
    [HttpPost]
    public async Task<IActionResult> Create([FromBody] CreateProspectRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.CreateAsync(userId.Value, orgId.Value, request);
            return CreatedAtAction(nameof(GetDetail), new { id = result.Prospect.ProspectId }, result);
        }
        catch (InvalidOperationException ex)
        {
            return ApiError(400, ex.Message);
        }
    }

    /// <summary>
    /// Search prospects with filters and pagination.
    /// </summary>
    [HttpGet]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> Search([FromQuery] ProspectSearchRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.SearchAsync(orgId.Value, request);
        return Ok(result);
    }

    /// <summary>
    /// Get full prospect detail including opportunity, notes, team, proposal, and score.
    /// </summary>
    [HttpGet("{id:int}")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetDetail(int id)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.GetDetailAsync(orgId.Value, id);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Update a prospect's status following the defined status flow.
    /// </summary>
    [HttpPatch("{id:int}/status")]
    public async Task<IActionResult> UpdateStatus(int id, [FromBody] UpdateProspectStatusRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.UpdateStatusAsync(orgId.Value, id, userId.Value, request);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return ApiError(400, ex.Message);
        }
    }

    /// <summary>
    /// Reassign a prospect to a different user.
    /// </summary>
    [HttpPatch("{id:int}/reassign")]
    public async Task<IActionResult> Reassign(int id, [FromBody] ReassignProspectRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.ReassignAsync(orgId.Value, id, userId.Value, request);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return ApiError(400, ex.Message);
        }
    }

    /// <summary>
    /// Add a note to a prospect.
    /// </summary>
    [HttpPost("{id:int}/notes")]
    public async Task<IActionResult> AddNote(int id, [FromBody] CreateProspectNoteRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.AddNoteAsync(orgId.Value, id, userId.Value, request);
            return StatusCode(201, result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return ApiError(400, ex.Message);
        }
    }

    /// <summary>
    /// Add a team member to a prospect.
    /// </summary>
    [HttpPost("{id:int}/team-members")]
    public async Task<IActionResult> AddTeamMember(int id, [FromBody] AddTeamMemberRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.AddTeamMemberAsync(orgId.Value, id, userId.Value, request);
            return StatusCode(201, result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// Remove a team member from a prospect.
    /// </summary>
    [HttpDelete("{id:int}/team-members/{memberId:int}")]
    public async Task<IActionResult> RemoveTeamMember(int id, int memberId)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var success = await _service.RemoveTeamMemberAsync(orgId.Value, id, memberId, userId.Value);
        return success ? NoContent() : NotFound();
    }

    /// <summary>
    /// Recalculate the Go/No-Go score for a prospect.
    /// </summary>
    [HttpPost("{id:int}/recalculate-score")]
    public async Task<IActionResult> RecalculateScore(int id)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.RecalculateScoreAsync(orgId.Value, id, userId.Value);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }
}
