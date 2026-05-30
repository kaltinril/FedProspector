using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/reference")]
[Authorize]
[EnableRateLimiting("search")]
public class ReferenceController : ApiControllerBase
{
    private readonly ICompanyProfileService _profileService;

    public ReferenceController(ICompanyProfileService profileService) => _profileService = profileService;

    /// <summary>
    /// Search NAICS codes by code or description. Returns up to 50 results.
    /// </summary>
    [HttpGet("naics")]
    public async Task<IActionResult> SearchNaics([FromQuery] string q)
    {
        if (string.IsNullOrWhiteSpace(q) || q.Length < 2)
            return Ok(Array.Empty<object>());

        var result = await _profileService.SearchNaicsAsync(q);
        return Ok(result);
    }

    /// <summary>
    /// Get NAICS code detail including SBA size standard information.
    /// </summary>
    [HttpGet("naics/{code}")]
    public async Task<IActionResult> GetNaicsDetail(string code)
    {
        var result = await _profileService.GetNaicsDetailAsync(code);
        if (result == null) return NotFound();

        return Ok(result);
    }

    /// <summary>
    /// Get the list of available certification types.
    /// </summary>
    [HttpGet("certifications")]
    public async Task<IActionResult> GetCertificationTypes()
    {
        var result = await _profileService.GetCertificationTypesAsync();
        return Ok(result);
    }

    /// <summary>
    /// Get the top-level 2-digit NAICS sectors (root of the hierarchy).
    /// </summary>
    [HttpGet("naics/sectors")]
    public async Task<IActionResult> GetNaicsSectors()
    {
        var result = await _profileService.GetNaicsSectorsAsync();
        return Ok(result);
    }

    /// <summary>
    /// Get the immediate children (next level down) of a NAICS code.
    /// </summary>
    [HttpGet("naics/{code}/children")]
    public async Task<IActionResult> GetNaicsChildren(string code)
    {
        var result = await _profileService.GetNaicsChildrenAsync(code);
        return Ok(result);
    }

    /// <summary>
    /// Get the ancestor chain for a NAICS code, from its sector down to the code (for breadcrumbs).
    /// </summary>
    [HttpGet("naics/{code}/ancestors")]
    public async Task<IActionResult> GetNaicsAncestors(string code)
    {
        var result = await _profileService.GetNaicsAncestorsAsync(code);
        if (result.Count == 0) return NotFound();

        return Ok(result);
    }
}
