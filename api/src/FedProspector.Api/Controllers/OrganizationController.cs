using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/org")]
[Authorize]
[EnableRateLimiting("write")]
public class OrganizationController : ApiControllerBase
{
    private readonly IOrganizationService _service;
    private readonly ICompanyProfileService _profileService;
    private readonly IOrganizationEntityService _entityService;

    public OrganizationController(
        IOrganizationService service,
        ICompanyProfileService profileService,
        IOrganizationEntityService entityService)
    {
        _service = service;
        _profileService = profileService;
        _entityService = entityService;
    }

    /// <summary>
    /// Get the current user's organization details.
    /// </summary>
    [HttpGet]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetOrganization()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetOrganizationAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Update the current user's organization name. Requires OrgAdmin role.
    /// </summary>
    [HttpPatch]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> UpdateOrganization([FromBody] UpdateOrganizationRequest request)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.UpdateOrganizationAsync(orgId.Value, request.Name);
        return Ok(result);
    }

    /// <summary>
    /// List members of the current user's organization.
    /// </summary>
    [HttpGet("members")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetMembers()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetMembersAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Create an invite for the current user's organization. Requires OrgAdmin role.
    /// </summary>
    [HttpPost("invites")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> CreateInvite([FromBody] CreateInviteRequest request)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var userId = GetCurrentUserId();
        if (userId is null) return Unauthorized();

        var result = await _service.CreateInviteAsync(orgId.Value, request.Email, request.OrgRole, userId.Value);
        return StatusCode(201, result);
    }

    /// <summary>
    /// List pending invites for the current user's organization. Requires OrgAdmin role.
    /// </summary>
    [HttpGet("invites")]
    [Authorize(Policy = "OrgAdmin")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetPendingInvites()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _service.GetPendingInvitesAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Revoke a pending invite. Requires OrgAdmin role.
    /// </summary>
    [HttpDelete("invites/{id:int}")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> RevokeInvite(int id)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        await _service.RevokeInviteAsync(orgId.Value, id);
        return NoContent();
    }

    // -----------------------------------------------------------------------
    // Company Profile Endpoints (Phase 20.8)
    // -----------------------------------------------------------------------

    /// <summary>
    /// Get the current organization's company profile.
    /// </summary>
    [HttpGet("profile")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetProfile()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _profileService.GetProfileAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Update the current organization's company profile. Requires OrgAdmin role.
    /// </summary>
    [HttpPut("profile")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> UpdateProfile([FromBody] UpdateOrgProfileRequest request)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _profileService.UpdateProfileAsync(orgId.Value, request);
        return Ok(result);
    }

    /// <summary>
    /// Get the organization's NAICS codes.
    /// </summary>
    [HttpGet("naics")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetNaics()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _profileService.GetNaicsAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Set (bulk replace) the organization's NAICS codes. Requires OrgAdmin role.
    /// </summary>
    [HttpPut("naics")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> SetNaics([FromBody] List<OrgNaicsDto> naicsCodes)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _profileService.SetNaicsAsync(orgId.Value, naicsCodes);
        return Ok(result);
    }

    /// <summary>
    /// Get the organization's certifications.
    /// </summary>
    [HttpGet("certifications")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetCertifications()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _profileService.GetCertificationsAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Set (bulk replace) the organization's certifications. Requires OrgAdmin role.
    /// </summary>
    [HttpPut("certifications")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> SetCertifications([FromBody] List<OrgCertificationDto> certifications)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _profileService.SetCertificationsAsync(orgId.Value, certifications);
        return Ok(result);
    }

    /// <summary>
    /// Get the organization's past performance records.
    /// </summary>
    [HttpGet("past-performance")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetPastPerformances()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _profileService.GetPastPerformancesAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Add a past performance record. Requires OrgAdmin role.
    /// </summary>
    [HttpPost("past-performance")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> AddPastPerformance([FromBody] CreatePastPerformanceRequest request)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _profileService.AddPastPerformanceAsync(orgId.Value, request);
        return StatusCode(201, result);
    }

    /// <summary>
    /// Delete a past performance record. Requires OrgAdmin role.
    /// </summary>
    [HttpDelete("past-performance/{id:int}")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> DeletePastPerformance(int id)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var deleted = await _profileService.DeletePastPerformanceAsync(orgId.Value, id);
        if (!deleted) return NotFound();

        return NoContent();
    }

    // -----------------------------------------------------------------------
    // Entity Linking Endpoints (Phase 91)
    // -----------------------------------------------------------------------

    /// <summary>
    /// Get all linked entities for the current organization.
    /// </summary>
    [HttpGet("entities")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetLinkedEntities()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _entityService.GetLinkedEntitiesAsync(orgId.Value);
        return Ok(result);
    }

    /// <summary>
    /// Link an entity to the current organization. Requires OrgAdmin role.
    /// </summary>
    [HttpPost("entities")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> LinkEntity([FromBody] LinkEntityRequest request)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var userId = GetCurrentUserId();
        if (userId is null) return Unauthorized();

        try
        {
            var result = await _entityService.LinkEntityAsync(orgId.Value, userId.Value, request);
            return StatusCode(201, result);
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return ApiError(400, ex.Message);
        }
    }

    /// <summary>
    /// Deactivate an entity link. Requires OrgAdmin role.
    /// </summary>
    [HttpDelete("entities/{linkId:int}")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> DeactivateEntityLink(int linkId)
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        try
        {
            await _entityService.DeactivateLinkAsync(orgId.Value, linkId);
            return NoContent();
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// Refresh organization profile from the linked SELF entity. Requires OrgAdmin role.
    /// </summary>
    [HttpPost("entities/refresh-self")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> RefreshFromSelfEntity()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        try
        {
            var result = await _entityService.RefreshFromSelfEntityAsync(orgId.Value);
            return Ok(result);
        }
        catch (InvalidOperationException ex)
        {
            return ApiError(400, ex.Message);
        }
    }

    /// <summary>
    /// Re-sync certifications from all linked entities for the current organization.
    /// </summary>
    [HttpPost("entities/resync-certs")]
    [Authorize(Policy = "OrgAdmin")]
    public async Task<IActionResult> ResyncCerts()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var count = await _entityService.SyncEntityCertsAsync(orgId.Value);
        return Ok(new { message = $"Re-synced {count} certifications from linked entities" });
    }

    /// <summary>
    /// Get aggregate NAICS codes across all linked entities and manual entries.
    /// </summary>
    [HttpGet("entities/aggregate-naics")]
    [EnableRateLimiting("search")]
    public async Task<IActionResult> GetAggregateNaics()
    {
        var orgId = GetCurrentOrganizationId();
        if (orgId is null) return Unauthorized();

        var result = await _entityService.GetAggregateNaicsAsync(orgId.Value);
        return Ok(result);
    }
}

