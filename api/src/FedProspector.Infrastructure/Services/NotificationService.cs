using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Notifications;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class NotificationService : INotificationService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<NotificationService> _logger;

    public NotificationService(FedProspectorDbContext context, ILogger<NotificationService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<NotificationListResponse> GetNotificationsAsync(int userId, NotificationListRequest request)
    {
        var query = _context.Notifications.AsNoTracking()
            .Where(n => n.UserId == userId);

        if (request.UnreadOnly)
            query = query.Where(n => n.IsRead == "N");

        if (!string.IsNullOrWhiteSpace(request.Type))
            query = query.Where(n => n.NotificationType == request.Type);

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderByDescending(n => n.CreatedAt)
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .Select(n => new NotificationDto
            {
                NotificationId = n.NotificationId,
                NotificationType = n.NotificationType,
                Title = n.Title,
                Message = n.Message,
                EntityType = n.EntityType,
                EntityId = n.EntityId,
                IsRead = n.IsRead == "Y",
                CreatedAt = n.CreatedAt,
                ReadAt = n.ReadAt
            })
            .ToListAsync();

        var unreadCount = await _context.Notifications.AsNoTracking()
            .CountAsync(n => n.UserId == userId && n.IsRead == "N");

        return new NotificationListResponse
        {
            Notifications = new PagedResponse<NotificationDto>
            {
                Items = items,
                Page = request.Page,
                PageSize = request.PageSize,
                TotalCount = totalCount
            },
            UnreadCount = unreadCount
        };
    }

    public async Task MarkAsReadAsync(int userId, int notificationId)
    {
        var notification = await _context.Notifications
            .FirstOrDefaultAsync(n => n.NotificationId == notificationId && n.UserId == userId);

        if (notification == null)
            throw new KeyNotFoundException($"Notification {notificationId} not found.");

        notification.IsRead = "Y";
        notification.ReadAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();
    }

    public async Task MarkAllAsReadAsync(int userId)
    {
        var unread = await _context.Notifications
            .Where(n => n.UserId == userId && n.IsRead == "N")
            .ToListAsync();

        foreach (var notification in unread)
        {
            notification.IsRead = "Y";
            notification.ReadAt = DateTime.UtcNow;
        }

        await _context.SaveChangesAsync();
    }

    public async Task<int> GetUnreadCountAsync(int userId)
    {
        return await _context.Notifications.AsNoTracking()
            .CountAsync(n => n.UserId == userId && n.IsRead == "N");
    }

    public async Task CreateNotificationAsync(
        int userId, string type, string title,
        string? message = null, string? entityType = null, string? entityId = null)
    {
        try
        {
            var notification = new Notification
            {
                UserId = userId,
                NotificationType = type,
                Title = title,
                Message = message,
                EntityType = entityType,
                EntityId = entityId,
                IsRead = "N",
                CreatedAt = DateTime.UtcNow
            };

            _context.Notifications.Add(notification);
            await _context.SaveChangesAsync();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create notification for user {UserId}: {Type} - {Title}",
                userId, type, title);
        }
    }
}
