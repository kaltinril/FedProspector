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
        return result != null ? Ok(result) : NotFound();
    }
}
