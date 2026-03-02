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

    public OpportunitiesController(IOpportunityService service)
    {
        _service = service;
    }

    [HttpGet]
    public async Task<IActionResult> Search([FromQuery] OpportunitySearchRequest request)
    {
        var result = await _service.SearchAsync(request);
        return Ok(result);
    }

    [HttpGet("targets")]
    public async Task<IActionResult> GetTargets([FromQuery] TargetOpportunitySearchRequest request)
    {
        var result = await _service.GetTargetsAsync(request);
        return Ok(result);
    }

    [HttpGet("{noticeId}")]
    public async Task<IActionResult> GetDetail(string noticeId)
    {
        var result = await _service.GetDetailAsync(noticeId);
        return result != null ? Ok(result) : NotFound();
    }
}
