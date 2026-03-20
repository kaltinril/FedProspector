using System.Text;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/opportunities")]
[Authorize]
[EnableRateLimiting("search")]
public class OpportunitiesController : ApiControllerBase
{
    private readonly IOpportunityService _service;
    private readonly IPWinService _pwinService;
    private readonly IRecommendedOpportunityService _recommendedService;
    private readonly IMarketIntelService _marketIntelService;
    private readonly IQualificationService _qualificationService;

    public OpportunitiesController(
        IOpportunityService service,
        IPWinService pwinService,
        IRecommendedOpportunityService recommendedService,
        IMarketIntelService marketIntelService,
        IQualificationService qualificationService)
    {
        _service = service;
        _pwinService = pwinService;
        _recommendedService = recommendedService;
        _marketIntelService = marketIntelService;
        _qualificationService = qualificationService;
    }

    [HttpGet]
    public async Task<IActionResult> Search([FromQuery] OpportunitySearchRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.SearchAsync(request, orgId.Value);
        return Ok(result);
    }

    [HttpGet("targets")]
    public async Task<IActionResult> GetTargets([FromQuery] TargetOpportunitySearchRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.GetTargetsAsync(request, orgId.Value);
        return Ok(result);
    }

    [HttpGet("{noticeId}")]
    public async Task<IActionResult> GetDetail(string noticeId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.GetDetailAsync(noticeId, orgId.Value);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Calculate probability of win (pWin) for an opportunity against the current org's profile.
    /// </summary>
    [HttpGet("{noticeId}/pwin")]
    public async Task<ActionResult<PWinResultDto>> CalculatePWin(string noticeId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _pwinService.CalculateAsync(noticeId, orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Calculate batch probability of win (pWin) for multiple opportunities.
    /// </summary>
    [HttpPost("pwin/batch")]
    public async Task<ActionResult<BatchPWinResponse>> CalculateBatchPWin([FromBody] BatchPWinRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        if (request.NoticeIds.Count > 25)
            return BadRequest("Batch pWin requests are limited to 25 notice IDs.");

        var result = await _pwinService.CalculateBatchAsync(request, orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Export opportunity search results as CSV.
    /// </summary>
    [HttpGet("export")]
    public async Task<IActionResult> ExportCsv([FromQuery] OpportunitySearchRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var csv = await _service.ExportCsvAsync(request, orgId.Value);
        var bytes = Encoding.UTF8.GetBytes(csv);
        return File(bytes, "text/csv", "opportunities_export.csv");
    }

    /// <summary>
    /// Get recommended opportunities scored and ranked for the current org's profile.
    /// </summary>
    [HttpGet("recommended")]
    public async Task<ActionResult<List<RecommendedOpportunityDto>>> GetRecommended(
        [FromQuery] int limit = 10)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _recommendedService.GetRecommendedAsync(orgId.Value, limit);
        return Ok(result);
    }

    /// <summary>
    /// Get incumbent analysis for an opportunity — identifies current contract holder and vulnerability signals.
    /// </summary>
    [HttpGet("{noticeId}/incumbent")]
    public async Task<ActionResult<IncumbentAnalysisDto>> GetIncumbentAnalysis(string noticeId)
    {
        var result = await _marketIntelService.GetIncumbentAnalysisAsync(noticeId);
        return Ok(result);
    }

    /// <summary>
    /// Get opportunity-scoped competitive landscape — agency + NAICS scoped market data with fallback.
    /// </summary>
    [HttpGet("{noticeId}/competitive-landscape")]
    public async Task<IActionResult> GetCompetitiveLandscape(string noticeId)
    {
        var result = await _marketIntelService.GetCompetitiveLandscapeAsync(noticeId);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Get set-aside shift analysis for an opportunity — compares current set-aside to predecessor contract.
    /// </summary>
    [HttpGet("{noticeId}/set-aside-shift")]
    public async Task<IActionResult> GetSetAsideShift(string noticeId)
    {
        var result = await _marketIntelService.GetSetAsideShiftAsync(noticeId);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Run qualification checks for an opportunity against the current org's profile.
    /// </summary>
    [HttpGet("{noticeId}/qualification")]
    public async Task<ActionResult<QualificationCheckDto>> CheckQualification(string noticeId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _qualificationService.CheckQualificationAsync(noticeId, orgId.Value);
        return Ok(result);
    }
}
