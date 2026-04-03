using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/teaming")]
[Authorize]
[EnableRateLimiting("search")]
public class TeamingController : ApiControllerBase
{
    private readonly ITeamingService _service;

    public TeamingController(ITeamingService service)
    {
        _service = service;
    }

    /// <summary>
    /// Search potential teaming partners with capability filters.
    /// </summary>
    [HttpGet("partners")]
    public async Task<ActionResult<PagedResponse<PartnerSearchResultDto>>> SearchPartners(
        [FromQuery] string? naicsCode = null,
        [FromQuery] string? state = null,
        [FromQuery] string? certification = null,
        [FromQuery] string? agencyCode = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 25)
    {
        if (page < 1) page = 1;
        if (pageSize < 1 || pageSize > 100) pageSize = 25;

        var result = await _service.SearchPartnersAsync(naicsCode, state, certification, agencyCode, page, pageSize);
        return Ok(result);
    }

    /// <summary>
    /// Returns risk assessment for a specific partner (traffic light: GREEN/YELLOW/RED).
    /// </summary>
    [HttpGet("partners/{uei}/risk")]
    public async Task<ActionResult<PartnerRiskDto>> GetPartnerRisk(string uei)
    {
        if (string.IsNullOrWhiteSpace(uei))
            return BadRequest("uei is required");

        var result = await _service.GetPartnerRiskAsync(uei);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Returns prime-sub relationship history for a specific entity.
    /// </summary>
    [HttpGet("partners/{uei}/relationships")]
    public async Task<ActionResult<PagedResponse<PrimeSubRelationshipDto>>> GetPrimeSubRelationships(
        string uei,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 25)
    {
        if (string.IsNullOrWhiteSpace(uei))
            return BadRequest("uei is required");

        if (page < 1) page = 1;
        if (pageSize < 1 || pageSize > 100) pageSize = 25;

        var result = await _service.GetPrimeSubRelationshipsAsync(uei, page, pageSize);
        return Ok(result);
    }

    /// <summary>
    /// Returns teaming network graph around a vendor (1 or 2 hops).
    /// </summary>
    [HttpGet("partners/{uei}/network")]
    public async Task<ActionResult<List<TeamingNetworkNodeDto>>> GetTeamingNetwork(
        string uei,
        [FromQuery] int depth = 1)
    {
        if (string.IsNullOrWhiteSpace(uei))
            return BadRequest("uei is required");

        if (depth < 1 || depth > 2) depth = 1;

        var result = await _service.GetTeamingNetworkAsync(uei, depth);
        return Ok(result);
    }

    /// <summary>
    /// Search for mentor-protege candidate pairings.
    /// </summary>
    [HttpGet("mentor-protege")]
    public async Task<ActionResult<PagedResponse<MentorProtegePairDto>>> GetMentorProtegeCandidates(
        [FromQuery] string? protegeUei = null,
        [FromQuery] string? naicsCode = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 25)
    {
        if (page < 1) page = 1;
        if (pageSize < 1 || pageSize > 100) pageSize = 25;

        var result = await _service.GetMentorProtegeCandidatesAsync(protegeUei, naicsCode, page, pageSize);
        return Ok(result);
    }

    /// <summary>
    /// Compare organization capabilities vs available partners to identify gaps.
    /// Requires authenticated user with organization context.
    /// </summary>
    [HttpGet("gap-analysis")]
    public async Task<ActionResult<PartnerGapAnalysisDto>> GetPartnerGapAnalysis(
        [FromQuery] string? naicsCode = null)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null)
            return Unauthorized();

        var result = await _service.GetPartnerGapAnalysisAsync(orgId.Value, naicsCode);
        return Ok(result);
    }
}
