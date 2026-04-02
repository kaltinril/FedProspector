using FedProspector.Core.DTOs.Pricing;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/pricing")]
[Authorize]
[EnableRateLimiting("search")]
public class PricingController : ApiControllerBase
{
    private readonly IPricingService _service;

    public PricingController(IPricingService service)
    {
        _service = service;
    }

    [HttpGet("labor-categories")]
    public async Task<IActionResult> GetCanonicalCategories([FromQuery] string? group = null)
    {
        var result = await _service.GetCanonicalCategoriesAsync(group);
        return Ok(result);
    }

    [HttpGet("labor-categories/search")]
    public async Task<IActionResult> SearchLaborCategories([FromQuery] string? q = null)
    {
        if (string.IsNullOrWhiteSpace(q))
            return BadRequest("Query parameter 'q' is required");

        var result = await _service.SearchLaborCategoriesAsync(q);
        return Ok(result);
    }

    [HttpGet("rate-heatmap")]
    public async Task<IActionResult> GetRateHeatmap([FromQuery] RateHeatmapRequest request)
    {
        var result = await _service.GetRateHeatmapAsync(request);
        return Ok(result);
    }

    [HttpGet("rate-distribution/{canonicalId:int}")]
    public async Task<IActionResult> GetRateDistribution(int canonicalId)
    {
        var result = await _service.GetRateDistributionAsync(canonicalId);
        return Ok(result);
    }

    [HttpPost("price-to-win")]
    public async Task<IActionResult> EstimatePriceToWin([FromBody] PriceToWinRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.NaicsCode))
            return BadRequest("NaicsCode is required");

        var result = await _service.EstimatePriceToWinAsync(request);
        return Ok(result);
    }

    [HttpGet("sub-benchmarks")]
    public async Task<IActionResult> GetSubBenchmarks([FromQuery] SubBenchmarkRequest request)
    {
        var result = await _service.GetSubBenchmarksAsync(request);
        return Ok(result);
    }

    [HttpGet("sub-ratios")]
    public async Task<IActionResult> GetSubRatios([FromQuery] string? naicsCode = null)
    {
        var result = await _service.GetSubRatiosAsync(naicsCode);
        return Ok(result);
    }

    [HttpGet("rate-trends")]
    public async Task<IActionResult> GetRateTrends([FromQuery] RateTrendRequest request)
    {
        if (request.CanonicalId <= 0)
            return BadRequest("CanonicalId is required");

        if (request.Years < 1 || request.Years > 20)
            request.Years = 5;

        var result = await _service.GetRateTrendsAsync(request);
        return Ok(result);
    }

    [HttpGet("escalation-forecast/{canonicalId:int}")]
    public async Task<IActionResult> GetEscalationForecast(int canonicalId, [FromQuery] int years = 5)
    {
        if (years < 1 || years > 20)
            years = 5;

        var result = await _service.GetEscalationForecastAsync(canonicalId, years);
        return Ok(result);
    }

    [HttpPost("igce-estimate")]
    public async Task<IActionResult> EstimateIgce([FromBody] IgceRequest request)
    {
        var result = await _service.EstimateIgceAsync(request);
        return Ok(result);
    }
}
