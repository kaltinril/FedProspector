using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/awards")]
[Authorize]
[EnableRateLimiting("search")]
public class AwardsController : ApiControllerBase
{
    private readonly IAwardService _service;
    private readonly IExpiringContractService _expiringService;
    private readonly IMarketIntelService _marketIntelService;

    public AwardsController(IAwardService service, IExpiringContractService expiringService, IMarketIntelService marketIntelService)
    {
        _service = service;
        _expiringService = expiringService;
        _marketIntelService = marketIntelService;
    }

    [HttpGet]
    public async Task<IActionResult> Search([FromQuery] AwardSearchRequest request)
    {
        var result = await _service.SearchAsync(request);
        return Ok(result);
    }

    [HttpGet("market-share")]
    public async Task<IActionResult> GetMarketShare(
        [FromQuery] string naicsCode,
        [FromQuery] int years = 3,
        [FromQuery] int limit = 10)
    {
        if (string.IsNullOrWhiteSpace(naicsCode))
            return BadRequest("naicsCode is required");

        if (years < 1 || years > 10)
            years = 3;

        if (limit < 1 || limit > 100)
            limit = 10;

        var result = await _marketIntelService.GetMarketShareAsync(naicsCode, years, limit);
        return Ok(result);
    }

    [HttpGet("expiring")]
    public async Task<ActionResult<List<ExpiringContractDto>>> GetExpiringContracts(
        [FromQuery] int monthsAhead = 12,
        [FromQuery] string? naicsCode = null,
        [FromQuery] string? setAsideType = null,
        [FromQuery] int limit = 20,
        [FromQuery] int offset = 0)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (!orgId.HasValue)
            return Unauthorized();

        if (monthsAhead < 1 || monthsAhead > 24)
            monthsAhead = 12;

        if (limit < 1 || limit > 100)
            limit = 20;

        if (offset < 0 || offset > 10000)
            offset = 0;

        var request = new ExpiringContractSearchRequest
        {
            MonthsAhead = monthsAhead,
            NaicsCode = naicsCode,
            SetAsideType = setAsideType,
            Limit = limit,
            Offset = offset
        };

        var result = await _expiringService.GetExpiringContractsAsync(orgId.Value, request);
        return Ok(result);
    }

    [HttpGet("{contractId}/burn-rate")]
    public async Task<IActionResult> GetBurnRate(string contractId)
    {
        var result = await _service.GetBurnRateAsync(contractId);
        return result != null ? Ok(result) : NotFound();
    }

    [HttpGet("{contractId}")]
    public async Task<IActionResult> GetDetail(string contractId)
    {
        var result = await _service.GetDetailAsync(contractId);
        return Ok(result);
    }

    [HttpPost("{contractId}/load")]
    public async Task<IActionResult> RequestLoad(string contractId, [FromBody] RequestLoadDto request)
    {
        var userId = GetCurrentUserId();
        var result = await _service.RequestLoadAsync(contractId, request.Tier, userId);
        return Ok(result);
    }

    [HttpGet("{contractId}/load-status")]
    public async Task<IActionResult> GetLoadStatus(string contractId)
    {
        var result = await _service.GetLoadStatusAsync(contractId);
        return result != null ? Ok(result) : Ok(new LoadRequestStatusDto());
    }
}
