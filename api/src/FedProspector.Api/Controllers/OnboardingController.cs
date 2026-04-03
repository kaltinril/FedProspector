using FedProspector.Core.DTOs.Onboarding;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/onboarding")]
[Authorize]
[EnableRateLimiting("search")]
public class OnboardingController : ApiControllerBase
{
    private readonly IOnboardingService _service;

    public OnboardingController(IOnboardingService service)
    {
        _service = service;
    }

    /// <summary>
    /// Get the current organization's profile completeness score and recommendations.
    /// </summary>
    [HttpGet("profile-completeness")]
    public async Task<IActionResult> GetProfileCompleteness()
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetProfileCompletenessAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Auto-import organization profile data from a SAM entity by UEI.
    /// </summary>
    [HttpPost("import-uei")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> ImportFromUei([FromBody] UeiImportRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        try
        {
            var result = await _service.ImportFromUeiAsync(orgId.Value, request.Uei);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// Get certification expiration alerts (within 90 days) for the current organization.
    /// </summary>
    [HttpGet("certification-alerts")]
    public async Task<IActionResult> GetCertificationAlerts()
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetCertificationAlertsAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Get SBA size standard proximity alerts for the current organization.
    /// </summary>
    [HttpGet("size-standard-alerts")]
    public async Task<IActionResult> GetSizeStandardAlerts()
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetSizeStandardAlertsAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Get relevance-ranked past performance records, optionally filtered to a specific opportunity.
    /// </summary>
    [HttpGet("past-performance-relevance")]
    public async Task<IActionResult> GetPastPerformanceRelevance([FromQuery] string? noticeId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetPastPerformanceRelevanceAsync(orgId.Value, noticeId);
        return Ok(result);
    }

    /// <summary>
    /// Get portfolio gap analysis for the current organization.
    /// </summary>
    [HttpGet("portfolio-gaps")]
    public async Task<IActionResult> GetPortfolioGaps()
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetPortfolioGapsAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// List PSC codes for the current organization.
    /// </summary>
    [HttpGet("psc-codes")]
    public async Task<IActionResult> GetPscCodes()
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetPscCodesAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Add a PSC code to the current organization. Requires OrgAdmin role.
    /// </summary>
    [HttpPost("psc-codes")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> AddPscCode([FromBody] OrganizationPscDto request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        try
        {
            var result = await _service.AddPscCodeAsync(orgId.Value, request.PscCode);
            return StatusCode(201, result);
        }
        catch (InvalidOperationException ex)
        {
            return ApiError(409, ex.Message);
        }
    }

    /// <summary>
    /// Remove a PSC code from the current organization. Requires OrgAdmin role.
    /// </summary>
    [HttpDelete("psc-codes/{id:int}")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> RemovePscCode(int id)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId is null) return Unauthorized();

        var deleted = await _service.RemovePscCodeAsync(orgId.Value, id);
        if (!deleted) return NotFound();

        return NoContent();
    }
}
