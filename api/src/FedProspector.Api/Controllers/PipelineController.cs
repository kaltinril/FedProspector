using FedProspector.Core.DTOs.Pipeline;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/pipeline")]
[Authorize]
[EnableRateLimiting("search")]
public class PipelineController : ApiControllerBase
{
    private readonly IPipelineService _service;

    public PipelineController(IPipelineService service)
    {
        _service = service;
    }

    /// <summary>
    /// Get pipeline funnel stats for the current organization.
    /// </summary>
    [HttpGet("funnel")]
    public async Task<IActionResult> GetFunnel()
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.GetFunnelAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Get pipeline calendar events with optional date range filter.
    /// </summary>
    [HttpGet("calendar")]
    public async Task<IActionResult> GetCalendarEvents(
        [FromQuery] DateTime? startDate, [FromQuery] DateTime? endDate)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.GetCalendarEventsAsync(orgId.Value, startDate, endDate);
        return Ok(result);
    }

    /// <summary>
    /// Get stale prospects that have not been updated recently.
    /// </summary>
    [HttpGet("stale")]
    public async Task<IActionResult> GetStaleProspects()
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.GetStaleProspectsAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Get revenue forecast by month for the pipeline.
    /// </summary>
    [HttpGet("forecast")]
    public async Task<IActionResult> GetRevenueForecast()
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.GetRevenueForecastAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// List milestones for a specific prospect.
    /// </summary>
    [HttpGet("prospects/{prospectId:int}/milestones")]
    public async Task<IActionResult> GetMilestones(int prospectId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.GetMilestonesAsync(prospectId, orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Create a milestone for a prospect.
    /// </summary>
    [HttpPost("prospects/{prospectId:int}/milestones")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> CreateMilestone(int prospectId, [FromBody] CreateMilestoneRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.CreateMilestoneAsync(prospectId, orgId.Value, request);
            return StatusCode(201, result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// Update a milestone.
    /// </summary>
    [HttpPut("milestones/{milestoneId:int}")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> UpdateMilestone(int milestoneId, [FromBody] UpdateMilestoneRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.UpdateMilestoneAsync(milestoneId, orgId.Value, request);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// Delete a milestone.
    /// </summary>
    [HttpDelete("milestones/{milestoneId:int}")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> DeleteMilestone(int milestoneId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var success = await _service.DeleteMilestoneAsync(milestoneId, orgId.Value);
        return success ? NoContent() : NotFound();
    }

    /// <summary>
    /// Auto-generate reverse timeline milestones from a response deadline.
    /// </summary>
    [HttpPost("prospects/{prospectId:int}/generate-timeline")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> GenerateReverseTimeline(
        int prospectId, [FromBody] ReverseTimelineRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        try
        {
            var result = await _service.GenerateReverseTimelineAsync(prospectId, orgId.Value, request);
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
    /// Bulk update status for multiple prospects at once.
    /// </summary>
    [HttpPost("bulk-status")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> BulkUpdateStatus([FromBody] BulkStatusUpdateRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.BulkUpdateStatusAsync(orgId.Value, userId.Value, request);
        return Ok(result);
    }
}
