using FedProspector.Core.DTOs.Entities;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace FedProspector.Api.Controllers;

[Route("api/v1/entities")]
[Authorize]
public class EntitiesController : ApiControllerBase
{
    private readonly IEntityService _service;

    public EntitiesController(IEntityService service)
    {
        _service = service;
    }

    [HttpGet]
    public async Task<IActionResult> Search([FromQuery] EntitySearchRequest request)
    {
        var result = await _service.SearchAsync(request);
        return Ok(result);
    }

    [HttpGet("{uei}/competitor-profile")]
    public async Task<IActionResult> GetCompetitorProfile(string uei)
    {
        var result = await _service.GetCompetitorProfileAsync(uei);
        return result != null ? Ok(result) : NotFound();
    }

    [HttpGet("{uei}/exclusion-check")]
    public async Task<IActionResult> CheckExclusion(string uei)
    {
        var result = await _service.CheckExclusionAsync(uei);
        return Ok(result);
    }

    [HttpGet("{uei}")]
    public async Task<IActionResult> GetDetail(string uei)
    {
        var result = await _service.GetDetailAsync(uei);
        return result != null ? Ok(result) : NotFound();
    }
}
