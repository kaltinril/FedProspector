using FedProspector.Core.DTOs.Insights;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/insights")]
[Authorize]
[EnableRateLimiting("search")]
public class InsightsController : ApiControllerBase
{
    private readonly IInsightsService _service;

    public InsightsController(IInsightsService service)
    {
        _service = service;
    }

    /// <summary>
    /// Find opportunities similar to the given notice by NAICS, agency, set-aside, and PSC.
    /// </summary>
    [HttpGet("similar-opportunities/{noticeId}")]
    public async Task<ActionResult<List<SimilarOpportunityDto>>> GetSimilarOpportunities(
        string noticeId,
        [FromQuery] int maxResults = 20)
    {
        if (string.IsNullOrWhiteSpace(noticeId))
            return BadRequest("noticeId is required");

        var result = await _service.GetSimilarOpportunitiesAsync(noticeId, maxResults);
        return Ok(result);
    }

    /// <summary>
    /// Composite data quality dashboard: freshness, completeness, and cross-source validation.
    /// </summary>
    [HttpGet("data-quality")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("admin")]
    public async Task<ActionResult<DataQualityDashboardDto>> GetDataQualityDashboard()
    {
        var result = await _service.GetDataQualityDashboardAsync();
        return Ok(result);
    }

    /// <summary>
    /// Per-source data freshness and load status.
    /// </summary>
    [HttpGet("data-quality/freshness")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("admin")]
    public async Task<ActionResult<List<DataFreshnessDto>>> GetDataFreshness()
    {
        var result = await _service.GetDataFreshnessAsync();
        return Ok(result);
    }

    /// <summary>
    /// Per-field completeness metrics for key tables.
    /// </summary>
    [HttpGet("data-quality/completeness")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("admin")]
    public async Task<ActionResult<List<DataCompletenessDto>>> GetDataCompleteness()
    {
        var result = await _service.GetDataCompletenessAsync();
        return Ok(result);
    }

    /// <summary>
    /// Cross-source data consistency validation checks.
    /// </summary>
    [HttpGet("data-quality/validation")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("admin")]
    public async Task<ActionResult<List<CrossSourceValidationDto>>> GetCrossSourceValidation()
    {
        var result = await _service.GetCrossSourceValidationAsync();
        return Ok(result);
    }

    /// <summary>
    /// Batch fetch competitor summaries for multiple prospects (for pipeline card enrichment).
    /// </summary>
    [HttpGet("prospect-competitors")]
    public async Task<ActionResult<List<ProspectCompetitorSummaryDto>>> GetProspectCompetitorSummaries(
        [FromQuery(Name = "prospectIds")] string? prospectIdsParam = null)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (!orgId.HasValue)
            return Unauthorized();

        if (string.IsNullOrWhiteSpace(prospectIdsParam))
            return BadRequest("prospectIds query parameter is required");

        var prospectIds = prospectIdsParam
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(s => int.TryParse(s, out var id) ? id : (int?)null)
            .Where(id => id.HasValue)
            .Select(id => id!.Value)
            .ToArray();

        if (prospectIds.Length == 0)
            return BadRequest("At least one valid prospect ID is required");

        if (prospectIds.Length > 100)
            return BadRequest("Maximum 100 prospect IDs per request");

        var result = await _service.GetProspectCompetitorSummariesAsync(orgId.Value, prospectIds);
        return Ok(result);
    }

    /// <summary>
    /// Single prospect competitor summary (org-scoped).
    /// </summary>
    [HttpGet("prospect-competitors/{prospectId:int}")]
    public async Task<ActionResult<ProspectCompetitorSummaryDto>> GetProspectCompetitorSummary(int prospectId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (!orgId.HasValue)
            return Unauthorized();

        // Fetch and verify org ownership via the view's organization_id column
        var result = await _service.GetProspectCompetitorSummaryAsync(prospectId);

        if (result == null)
            return NotFound();

        // The view joins prospect (which has organization_id). Verify ownership
        // by checking the result came from the correct org. Since the view model
        // doesn't include org_id in the DTO, we re-query with org filter.
        var results = await _service.GetProspectCompetitorSummariesAsync(orgId.Value, [prospectId]);
        if (results.Count == 0)
            return NotFound();

        return Ok(results[0]);
    }
}
