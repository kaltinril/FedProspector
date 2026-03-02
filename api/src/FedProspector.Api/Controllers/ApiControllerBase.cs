using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Core.DTOs;
using FedProspector.Infrastructure.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace FedProspector.Api.Controllers;

[ApiController]
public abstract class ApiControllerBase : ControllerBase
{
    protected int? GetCurrentUserId()
    {
        var claim = User.FindFirst(JwtRegisteredClaimNames.Sub)
                    ?? User.FindFirst(ClaimTypes.NameIdentifier);
        return claim != null && int.TryParse(claim.Value, out var id) ? id : null;
    }

    protected int? GetCurrentOrganizationId()
    {
        var claim = User.FindFirst("org_id");
        return claim != null && int.TryParse(claim.Value, out var id) ? id : null;
    }

    /// <summary>
    /// Resolves the current user's organization ID from JWT claim or DB lookup.
    /// Returns null if user cannot be resolved.
    /// </summary>
    protected async Task<int?> ResolveOrganizationIdAsync()
    {
        // Try JWT claim first (set by auth overhaul)
        var orgId = GetCurrentOrganizationId();
        if (orgId.HasValue) return orgId;

        // Fallback: look up from user record
        var userId = GetCurrentUserId();
        if (!userId.HasValue) return null;

        var db = HttpContext.RequestServices.GetRequiredService<FedProspectorDbContext>();
        var user = await db.AppUsers.AsNoTracking()
            .FirstOrDefaultAsync(u => u.UserId == userId.Value);
        return user?.OrganizationId;
    }

    protected string? GetCurrentUserEmail()
    {
        return User.FindFirst(ClaimTypes.Email)?.Value;
    }

    protected bool IsAdmin()
    {
        return User.IsInRole("admin");
    }

    protected IActionResult ApiError(int statusCode, string message, string? detail = null)
    {
        return StatusCode(statusCode, new ApiErrorResponse
        {
            StatusCode = statusCode,
            Message = message,
            Detail = detail,
            TraceId = HttpContext.TraceIdentifier
        });
    }
}
