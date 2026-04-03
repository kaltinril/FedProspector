using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/competitive-intel")]
[Authorize]
[EnableRateLimiting("search")]
public class CompetitiveIntelController : ApiControllerBase
{
    private readonly ICompetitiveIntelService _service;

    public CompetitiveIntelController(ICompetitiveIntelService service)
    {
        _service = service;
    }

    /// <summary>
    /// Returns contracts likely to be re-competed in 12-18 months, with optional filters.
    /// </summary>
    [HttpGet("recompete-candidates")]
    public async Task<ActionResult<PagedResponse<RecompeteCandidateDto>>> GetRecompeteCandidates(
        [FromQuery] string? naicsCode = null,
        [FromQuery] string? agencyCode = null,
        [FromQuery] string? setAsideCode = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 25)
    {
        if (page < 1) page = 1;
        if (pageSize < 1 || pageSize > 100) pageSize = 25;

        var result = await _service.GetRecompeteCandidatesAsync(naicsCode, agencyCode, setAsideCode, page, pageSize);
        return Ok(result);
    }

    /// <summary>
    /// Returns agency/office re-compete behavioral patterns (incumbent retention, new entrant rates, etc.).
    /// </summary>
    [HttpGet("agency-patterns")]
    public async Task<ActionResult<List<AgencyRecompetePatternDto>>> GetAgencyRecompetePatterns(
        [FromQuery] string? agencyCode = null,
        [FromQuery] string? officeCode = null)
    {
        var result = await _service.GetAgencyRecompetePatternsAsync(agencyCode, officeCode);
        return Ok(result);
    }

    /// <summary>
    /// Returns buying pattern data for a specific agency, broken down by year and quarter.
    /// </summary>
    [HttpGet("agency-patterns/{agencyCode}")]
    public async Task<ActionResult<List<AgencyBuyingPatternDto>>> GetAgencyBuyingPatterns(
        string agencyCode,
        [FromQuery] int? year = null)
    {
        if (string.IsNullOrWhiteSpace(agencyCode))
            return BadRequest("agencyCode is required");

        var result = await _service.GetAgencyBuyingPatternsAsync(agencyCode, year);
        return Ok(result);
    }

    /// <summary>
    /// Returns a comprehensive competitor dossier for a specific vendor by UEI.
    /// </summary>
    [HttpGet("competitor/{uei}")]
    public async Task<ActionResult<CompetitorDossierDto>> GetCompetitorDossier(string uei)
    {
        if (string.IsNullOrWhiteSpace(uei))
            return BadRequest("uei is required");

        var result = await _service.GetCompetitorDossierAsync(uei);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Searches contracting offices with optional agency and text filters.
    /// </summary>
    [HttpGet("offices")]
    public async Task<ActionResult<PagedResponse<ContractingOfficeProfileDto>>> SearchContractingOffices(
        [FromQuery] string? agencyCode = null,
        [FromQuery] string? search = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 25)
    {
        if (page < 1) page = 1;
        if (pageSize < 1 || pageSize > 100) pageSize = 25;

        var result = await _service.SearchContractingOfficesAsync(agencyCode, search, page, pageSize);
        return Ok(result);
    }

    /// <summary>
    /// Returns a detailed profile for a specific contracting office.
    /// </summary>
    [HttpGet("offices/{officeCode}")]
    public async Task<ActionResult<ContractingOfficeProfileDto>> GetContractingOfficeProfile(string officeCode)
    {
        if (string.IsNullOrWhiteSpace(officeCode))
            return BadRequest("officeCode is required");

        var result = await _service.GetContractingOfficeProfileAsync(officeCode);
        return result != null ? Ok(result) : NotFound();
    }
}
