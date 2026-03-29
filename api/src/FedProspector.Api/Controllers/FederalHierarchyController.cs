using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.FederalHierarchy;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/hierarchy")]
[Authorize]
[EnableRateLimiting("search")]
public class FederalHierarchyController : ApiControllerBase
{
    private readonly IFederalHierarchyService _service;

    public FederalHierarchyController(IFederalHierarchyService service)
    {
        _service = service;
    }

    /// <summary>
    /// Search/list federal organizations with filters and pagination.
    /// </summary>
    [HttpGet]
    public async Task<IActionResult> Search([FromQuery] FederalOrgSearchRequestDto request)
    {
        var result = await _service.SearchAsync(request);
        return Ok(result);
    }

    /// <summary>
    /// Get a single organization's detail including parent chain breadcrumbs.
    /// </summary>
    [HttpGet("{fhOrgId:int}")]
    public async Task<IActionResult> GetDetail(int fhOrgId)
    {
        var result = await _service.GetDetailAsync(fhOrgId);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Get direct children of an organization.
    /// </summary>
    [HttpGet("{fhOrgId:int}/children")]
    public async Task<IActionResult> GetChildren(int fhOrgId, [FromQuery] string? status = null, [FromQuery] string? keyword = null)
    {
        var result = await _service.GetChildrenAsync(fhOrgId, status, keyword);
        return Ok(result);
    }

    /// <summary>
    /// Get top-level departments with child/descendant counts for tree root.
    /// </summary>
    [HttpGet("tree")]
    public async Task<IActionResult> GetTree([FromQuery] string? keyword = null)
    {
        var result = await _service.GetTreeAsync(keyword);
        return Ok(result);
    }

    /// <summary>
    /// Get opportunities linked to this organization and its descendants.
    /// </summary>
    [HttpGet("{fhOrgId:int}/opportunities")]
    public async Task<IActionResult> GetOpportunities(int fhOrgId, [FromQuery] PagedRequest request, [FromQuery] string? active = null, [FromQuery] string? type = null, [FromQuery] string? setAsideCode = null)
    {
        var result = await _service.GetOpportunitiesAsync(fhOrgId, request, active, type, setAsideCode);
        return Ok(result);
    }

    /// <summary>
    /// Trigger a hierarchy data refresh. System Admin only.
    /// </summary>
    [HttpPost("refresh")]
    [Authorize(Policy = "SystemAdmin")]
    public IActionResult TriggerRefresh([FromBody] HierarchyRefreshRequestDto request)
    {
        // Stub: full subprocess/poller integration deferred to Phase 110Y.
        // Validate the request for future use.
        if (request.Level is not ("hierarchy" or "offices" or "full"))
            return BadRequest("Level must be 'hierarchy', 'offices', or 'full'.");

        if (request.ApiKey is not (1 or 2))
            return BadRequest("ApiKey must be 1 or 2.");

        return ApiError(501, "Hierarchy refresh via API is not yet implemented. Use the CLI: python ./fed_prospector/main.py load hierarchy");
    }

    /// <summary>
    /// Check the status of the last hierarchy refresh job.
    /// </summary>
    [HttpGet("refresh/status")]
    public async Task<IActionResult> GetRefreshStatus()
    {
        var result = await _service.GetRefreshStatusAsync();
        return Ok(result);
    }
}
