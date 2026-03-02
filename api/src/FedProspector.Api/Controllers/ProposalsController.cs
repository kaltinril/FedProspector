using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Exceptions;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/proposals")]
[Authorize]
[EnableRateLimiting("write")]
public class ProposalsController : ApiControllerBase
{
    private readonly IProposalService _service;

    public ProposalsController(IProposalService service) => _service = service;

    /// <summary>
    /// List/search proposals with pagination (org-wide, cross-prospect views).
    /// </summary>
    [HttpGet]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> List([FromQuery] ProposalSearchRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.ListAsync(orgId.Value, request);
        return Ok(result);
    }

    /// <summary>
    /// Create a new proposal linked to a prospect.
    /// </summary>
    [HttpPost]
    public async Task<IActionResult> Create([FromBody] CreateProposalRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.CreateAsync(userId.Value, orgId.Value, request);
        return StatusCode(201, result);
    }

    /// <summary>
    /// Update a proposal (status, estimated value, win probability, lessons learned).
    /// </summary>
    [HttpPatch("{id:int}")]
    public async Task<IActionResult> Update(int id, [FromBody] UpdateProposalRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.UpdateAsync(orgId.Value, id, userId.Value, request);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
        catch (ConflictException ex)
        {
            return ApiError(409, ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return ApiError(400, ex.Message);
        }
    }

    /// <summary>
    /// Add a document record to a proposal.
    /// </summary>
    [HttpPost("{id:int}/documents")]
    public async Task<IActionResult> AddDocument(int id, [FromBody] AddProposalDocumentRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.AddDocumentAsync(orgId.Value, id, userId.Value, request);
            return StatusCode(201, result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// List milestones for a proposal.
    /// </summary>
    [HttpGet("{id:int}/milestones")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetMilestones(int id)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.GetMilestonesAsync(orgId.Value, id);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// Create a milestone for a proposal.
    /// </summary>
    [HttpPost("{id:int}/milestones")]
    public async Task<IActionResult> CreateMilestone(int id, [FromBody] CreateMilestoneRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.CreateMilestoneAsync(orgId.Value, id, userId.Value, request);
            return StatusCode(201, result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// Update a milestone within a proposal.
    /// </summary>
    [HttpPatch("{id:int}/milestones/{milestoneId:int}")]
    public async Task<IActionResult> UpdateMilestone(int id, int milestoneId, [FromBody] UpdateMilestoneRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.UpdateMilestoneAsync(orgId.Value, id, milestoneId, userId.Value, request);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }
}
