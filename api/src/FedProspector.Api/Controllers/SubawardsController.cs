using FedProspector.Core.DTOs.Subawards;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/subawards")]
[Authorize]
[EnableRateLimiting("search")]
public class SubawardsController : ApiControllerBase
{
    private readonly ISubawardService _service;

    public SubawardsController(ISubawardService service)
    {
        _service = service;
    }

    /// <summary>
    /// Search for teaming partners based on subaward history.
    /// </summary>
    [HttpGet("teaming-partners")]
    public async Task<IActionResult> GetTeamingPartners([FromQuery] TeamingPartnerSearchRequest request)
    {
        var result = await _service.GetTeamingPartnersAsync(request);
        return Ok(result);
    }

    /// <summary>
    /// Get subawards for a specific prime contract.
    /// </summary>
    [HttpGet("by-prime/{primePiid}")]
    public async Task<IActionResult> GetByPrimeContract(string primePiid)
    {
        var result = await _service.GetSubawardsByPrimeContractAsync(Uri.UnescapeDataString(primePiid));
        return Ok(result);
    }
}
