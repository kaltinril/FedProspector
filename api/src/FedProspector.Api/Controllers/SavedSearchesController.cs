using FedProspector.Core.DTOs.SavedSearches;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace FedProspector.Api.Controllers;

[Route("api/v1/saved-searches")]
[Authorize]
public class SavedSearchesController : ApiControllerBase
{
    private readonly ISavedSearchService _service;

    public SavedSearchesController(ISavedSearchService service)
    {
        _service = service;
    }

    /// <summary>
    /// List all active saved searches for the current user.
    /// </summary>
    [HttpGet]
    public async Task<IActionResult> List()
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var results = await _service.ListAsync(userId.Value);
        return Ok(results);
    }

    /// <summary>
    /// Create a new saved search.
    /// </summary>
    [HttpPost]
    public async Task<IActionResult> Create([FromBody] CreateSavedSearchRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var result = await _service.CreateAsync(userId.Value, request);
        return CreatedAtAction(nameof(List), result);
    }

    /// <summary>
    /// Execute a saved search and return matching opportunities.
    /// </summary>
    [HttpPost("{id:int}/run")]
    public async Task<IActionResult> Run(int id)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var result = await _service.RunAsync(userId.Value, id);
        return result != null ? Ok(result) : NotFound();
    }

    /// <summary>
    /// Soft-delete a saved search (sets IsActive to N).
    /// </summary>
    [HttpDelete("{id:int}")]
    public async Task<IActionResult> Delete(int id)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();
        var success = await _service.DeleteAsync(userId.Value, id);
        return success ? NoContent() : NotFound();
    }
}
