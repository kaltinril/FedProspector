using System.Security.Claims;
using FedProspector.Core.DTOs;
using Microsoft.AspNetCore.Mvc;

namespace FedProspector.Api.Controllers;

[ApiController]
public abstract class ApiControllerBase : ControllerBase
{
    protected int? GetCurrentUserId()
    {
        var claim = User.FindFirst(ClaimTypes.NameIdentifier);
        return claim != null ? int.Parse(claim.Value) : null;
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
