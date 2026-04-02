using System.Text;
using FedProspector.Core.DTOs.Awards;
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
    private readonly IAttachmentIntelService _attachmentIntelService;
    private readonly IIncumbentVulnerabilityService _incumbentVulnerabilityService;
    private readonly ICompetitorStrengthService _competitorStrengthService;
    private readonly IPartnerCompatibilityService _partnerCompatibilityService;
    private readonly IOpenDoorService _openDoorService;
    private readonly IPursuitPriorityService _pursuitPriorityService;
    private readonly IOpportunityIgnoreService _ignoreService;

    public OpportunitiesController(
        IOpportunityService service,
        IPWinService pwinService,
        IRecommendedOpportunityService recommendedService,
        IMarketIntelService marketIntelService,
        IQualificationService qualificationService,
        IAttachmentIntelService attachmentIntelService,
        IIncumbentVulnerabilityService incumbentVulnerabilityService,
        ICompetitorStrengthService competitorStrengthService,
        IPartnerCompatibilityService partnerCompatibilityService,
        IOpenDoorService openDoorService,
        IPursuitPriorityService pursuitPriorityService,
        IOpportunityIgnoreService ignoreService)
    {
        _service = service;
        _pwinService = pwinService;
        _recommendedService = recommendedService;
        _marketIntelService = marketIntelService;
        _qualificationService = qualificationService;
        _attachmentIntelService = attachmentIntelService;
        _incumbentVulnerabilityService = incumbentVulnerabilityService;
        _competitorStrengthService = competitorStrengthService;
        _partnerCompatibilityService = partnerCompatibilityService;
        _openDoorService = openDoorService;
        _pursuitPriorityService = pursuitPriorityService;
        _ignoreService = ignoreService;
    }

    [HttpGet]
    public async Task<IActionResult> Search([FromQuery] OpportunitySearchRequest request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var userId = GetCurrentUserId();
        var result = await _service.SearchAsync(request, orgId.Value, userId);
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
    /// Fetch a missing opportunity description from SAM.gov on demand.
    /// If already populated, returns the cached text without making an API call.
    /// </summary>
    [HttpPost("{noticeId}/fetch-description")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> FetchDescription(string noticeId)
    {
        var (descriptionText, error, notFound) = await _service.FetchDescriptionAsync(noticeId);

        if (notFound && error == null)
            return NotFound(new { message = "Opportunity not found." });

        if (notFound && error != null)
            return NotFound(new { message = error });

        if (error != null)
            return ApiError(502, error);

        return Ok(new { noticeId, descriptionText });
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

        if (request.NoticeIds.Count > 200)
            return BadRequest("Batch pWin requests are limited to 200 notice IDs.");

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

        var userId = GetCurrentUserId();
        var csv = await _service.ExportCsvAsync(request, orgId.Value, userId);
        var bytes = Encoding.UTF8.GetBytes(csv);
        return File(bytes, "text/csv", "opportunities_export.csv");
    }

    // ────────────────────────────────────────────────────────────────────
    // Ignore / Un-ignore
    // ────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Ignore an opportunity so it no longer appears in search or recommendations.
    /// </summary>
    [HttpPost("{noticeId}/ignore")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> Ignore(string noticeId, [FromBody] IgnoreOpportunityRequest? request = null)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();

        var result = await _ignoreService.IgnoreAsync(userId.Value, noticeId, request?.Reason);
        return Ok(new { result.NoticeId, result.IgnoredAt, result.Reason });
    }

    /// <summary>
    /// Un-ignore a previously ignored opportunity.
    /// </summary>
    [HttpDelete("{noticeId}/ignore")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> Unignore(string noticeId)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();

        await _ignoreService.UnignoreAsync(userId.Value, noticeId);
        return NoContent();
    }

    /// <summary>
    /// Get the set of notice IDs the current user has ignored.
    /// </summary>
    [HttpGet("ignored")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetIgnoredIds()
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();

        var ids = await _ignoreService.GetIgnoredNoticeIdsAsync(userId.Value);
        return Ok(ids);
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

        var userId = GetCurrentUserId();
        var result = await _recommendedService.GetRecommendedAsync(orgId.Value, limit, userId);
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

    /// <summary>
    /// Get document intelligence extracted from opportunity attachments (SOW, RFP, etc.).
    /// </summary>
    [HttpGet("{noticeId}/document-intelligence")]
    public async Task<IActionResult> GetDocumentIntelligence(string noticeId)
    {
        var result = await _attachmentIntelService.GetDocumentIntelligenceAsync(noticeId);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Get federal identifiers extracted from opportunity attachments (PIIDs, UEIs, CAGE codes, etc.)
    /// and predecessor contract candidates.
    /// </summary>
    [HttpGet("{noticeId}/identifier-refs")]
    public async Task<IActionResult> GetIdentifierRefs(string noticeId)
    {
        var result = await _attachmentIntelService.GetIdentifierRefsAsync(noticeId);
        return Ok(result);
    }

    /// <summary>
    /// Get a cost estimate for AI analysis of opportunity attachments.
    /// </summary>
    [HttpGet("{noticeId}/analyze/estimate")]
    public async Task<ActionResult<AnalysisEstimateDto>> GetAnalysisEstimate(
        string noticeId, [FromQuery] string model = "haiku")
    {
        var estimate = await _attachmentIntelService.GetAnalysisEstimateAsync(noticeId, model);
        return Ok(estimate);
    }

    /// <summary>
    /// Get the status of the most recent analysis request for an opportunity.
    /// </summary>
    [DisableRateLimiting]
    [HttpGet("{noticeId}/analyze/status")]
    public async Task<ActionResult<LoadRequestStatusDto>> GetAnalysisStatus(string noticeId)
    {
        var result = await _attachmentIntelService.GetAnalysisStatusAsync(noticeId);
        return result != null ? Ok(result) : Ok(new LoadRequestStatusDto());
    }

    /// <summary>
    /// Request analysis of opportunity attachments. Inserts a data_load_request for the Python pipeline.
    /// </summary>
    [HttpPost("{noticeId}/analyze")]
    [EnableRateLimiting("write")]
    public async Task<ActionResult<LoadRequestStatusDto>> RequestAnalysis(
        string noticeId, [FromQuery] string tier = "haiku")
    {
        var userId = GetCurrentUserId();
        var result = await _attachmentIntelService.RequestAnalysisAsync(noticeId, tier, userId);
        return Ok(result);
    }

    /// <summary>
    /// Request analysis of a single attachment (keyword extraction or AI).
    /// </summary>
    [HttpPost("{noticeId}/attachments/{attachmentId:int}/analyze")]
    [EnableRateLimiting("write")]
    public async Task<ActionResult<LoadRequestStatusDto>> RequestAttachmentAnalysis(
        string noticeId, int attachmentId, [FromQuery] string tier = "ai")
    {
        var userId = GetCurrentUserId();
        var result = await _attachmentIntelService.RequestAttachmentAnalysisAsync(noticeId, attachmentId, tier, userId);
        return Ok(result);
    }

    /// <summary>
    /// Get status of the most recent single-attachment analysis request.
    /// </summary>
    [DisableRateLimiting]
    [HttpGet("{noticeId}/attachments/{attachmentId:int}/analyze/status")]
    public async Task<ActionResult<LoadRequestStatusDto>> GetAttachmentAnalysisStatus(
        string noticeId, int attachmentId)
    {
        var result = await _attachmentIntelService.GetAttachmentAnalysisStatusAsync(attachmentId);
        return result != null ? Ok(result) : Ok(new LoadRequestStatusDto());
    }

    // ────────────────────────────────────────────────────────────────────
    // Incumbent Vulnerability Score (IVS)
    // ────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Calculate incumbent vulnerability score for an opportunity.
    /// </summary>
    [HttpGet("{noticeId}/ivs")]
    public async Task<ActionResult<IvsResultDto>> GetIncumbentVulnerability(string noticeId)
    {
        var result = await _incumbentVulnerabilityService.CalculateAsync(noticeId);
        return Ok(result);
    }

    // ────────────────────────────────────────────────────────────────────
    // Competitor Strength
    // ────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Get competitor strength analysis for a specific opportunity.
    /// </summary>
    [HttpGet("{noticeId}/competitors")]
    public async Task<ActionResult<CompetitorAnalysisDto>> GetOpportunityCompetitors(string noticeId)
    {
        var result = await _competitorStrengthService.GetOpportunityCompetitorsAsync(noticeId);
        return Ok(result);
    }

    /// <summary>
    /// Get competitor strength analysis for a NAICS code (market-level).
    /// </summary>
    [HttpGet("market/competitors/{naicsCode}")]
    public async Task<ActionResult<CompetitorAnalysisDto>> GetMarketCompetitors(
        string naicsCode, [FromQuery] int years = 3, [FromQuery] int limit = 10)
    {
        var result = await _competitorStrengthService.GetMarketCompetitorsAsync(naicsCode, years, limit);
        return Ok(result);
    }

    /// <summary>
    /// Get detailed competitor strength for a single competitor.
    /// </summary>
    [HttpGet("competitors/{competitorUei}")]
    public async Task<IActionResult> GetCompetitorDetail(
        string competitorUei, [FromQuery] string? naicsCode = null, [FromQuery] string? agencyCode = null)
    {
        var result = await _competitorStrengthService.GetCompetitorDetailAsync(competitorUei, naicsCode, agencyCode);
        return result != null ? Ok(result) : NotFound();
    }

    // ────────────────────────────────────────────────────────────────────
    // Partner Compatibility
    // ────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Find and score potential partners for an opportunity.
    /// </summary>
    [HttpGet("{noticeId}/partners")]
    public async Task<ActionResult<PartnerAnalysisDto>> FindPartners(string noticeId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _partnerCompatibilityService.FindPartnersAsync(noticeId, orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Score a specific partner for a specific opportunity.
    /// </summary>
    [HttpGet("{noticeId}/partners/{partnerUei}")]
    public async Task<ActionResult<PartnerScoreDto>> ScorePartner(string noticeId, string partnerUei)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _partnerCompatibilityService.ScorePartnerAsync(partnerUei, noticeId, orgId.Value);
        return Ok(result);
    }

    // ────────────────────────────────────────────────────────────────────
    // Open Door
    // ────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Find primes with best Open Door scores in a NAICS code.
    /// </summary>
    [HttpGet("market/open-door/{naicsCode}")]
    public async Task<ActionResult<OpenDoorAnalysisDto>> FindOpenDoorPrimes(
        string naicsCode, [FromQuery] int years = 3, [FromQuery] int limit = 10)
    {
        var result = await _openDoorService.FindOpenDoorPrimesAsync(naicsCode, years, limit);
        return Ok(result);
    }

    /// <summary>
    /// Score a specific prime contractor's small business engagement.
    /// </summary>
    [HttpGet("market/open-door/prime/{primeUei}")]
    public async Task<ActionResult<OpenDoorScoreDto>> ScorePrime(
        string primeUei, [FromQuery] int years = 3)
    {
        var result = await _openDoorService.ScorePrimeAsync(primeUei, years);
        return Ok(result);
    }

    // ────────────────────────────────────────────────────────────────────
    // Pursuit Priority
    // ────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Calculate pursuit priority score for an opportunity (combined pWin + OQS).
    /// </summary>
    [HttpGet("{noticeId}/pursuit-priority")]
    public async Task<ActionResult<PursuitPriorityDto>> GetPursuitPriority(string noticeId)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _pursuitPriorityService.CalculateAsync(noticeId, orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Calculate pursuit priority scores for multiple opportunities.
    /// </summary>
    [HttpPost("pursuit-priority/batch")]
    public async Task<ActionResult<List<PursuitPriorityDto>>> CalculateBatchPursuitPriority(
        [FromBody] List<string> noticeIds)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        if (noticeIds.Count > 200)
            return BadRequest("Batch pursuit priority requests are limited to 200 notice IDs.");

        var result = await _pursuitPriorityService.CalculateBatchAsync(noticeIds, orgId.Value);
        return Ok(result);
    }
}
