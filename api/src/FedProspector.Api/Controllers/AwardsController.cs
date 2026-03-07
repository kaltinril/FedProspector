using FedProspector.Core.DTOs.Awards;
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

    public AwardsController(IAwardService service)
    {
        _service = service;
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
        [FromQuery] int limit = 10)
    {
        if (string.IsNullOrWhiteSpace(naicsCode))
            return BadRequest("naicsCode is required");

        if (limit < 1 || limit > 50)
            limit = 10;

        var result = await _service.GetMarketShareAsync(naicsCode, limit);
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
