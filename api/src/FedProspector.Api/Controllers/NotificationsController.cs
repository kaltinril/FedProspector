using FedProspector.Core.DTOs.Notifications;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/notifications")]
[Authorize]
[EnableRateLimiting("search")]
public class NotificationsController : ApiControllerBase
{
    private readonly INotificationService _service;

    public NotificationsController(INotificationService service) => _service = service;

    /// <summary>
    /// List notifications for the current user with optional filters.
    /// </summary>
    [HttpGet]
    public async Task<IActionResult> List([FromQuery] NotificationListRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();

        var result = await _service.GetNotificationsAsync(userId.Value, request);
        return Ok(result);
    }

    /// <summary>
    /// Mark a single notification as read.
    /// </summary>
    [HttpPatch("{id:int}/read")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> MarkAsRead(int id)
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();

        try
        {
            await _service.MarkAsReadAsync(userId.Value, id);
            return Ok(new { message = "Notification marked as read." });
        }
        catch (KeyNotFoundException ex)
        {
            return ApiError(404, ex.Message);
        }
    }

    /// <summary>
    /// Mark all notifications as read for the current user.
    /// </summary>
    [HttpPost("mark-all-read")]
    [EnableRateLimiting("write")]
    public async Task<IActionResult> MarkAllAsRead()
    {
        var userId = GetCurrentUserId();
        if (userId == null) return Unauthorized();

        await _service.MarkAllAsReadAsync(userId.Value);
        return Ok(new { message = "All notifications marked as read." });
    }
}
