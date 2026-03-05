using FedProspector.Core.DTOs.Notifications;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class NotificationServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly NotificationService _service;

    public NotificationServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new NotificationService(_context, NullLogger<NotificationService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    private void SeedNotification(int userId, string type, string title,
        bool isRead = false, string? message = null)
    {
        _context.Notifications.Add(new Notification
        {
            UserId = userId,
            NotificationType = type,
            Title = title,
            Message = message,
            IsRead = isRead ? "Y" : "N",
            ReadAt = isRead ? DateTime.UtcNow : null,
            CreatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    // --- GetNotificationsAsync tests ---

    [Fact]
    public async Task GetNotificationsAsync_ReturnsUserNotifications()
    {
        SeedNotification(1, "INFO", "Notification 1");
        SeedNotification(1, "ALERT", "Notification 2");
        SeedNotification(2, "INFO", "Other user notification"); // different user

        var request = new NotificationListRequest { Page = 1, PageSize = 25, UnreadOnly = false };
        var result = await _service.GetNotificationsAsync(1, request);

        result.Notifications.TotalCount.Should().Be(2);
        result.Notifications.Items.Should().HaveCount(2);
    }

    // --- MarkAsReadAsync tests ---

    [Fact]
    public async Task MarkAsReadAsync_ExistingNotification_MarksRead()
    {
        SeedNotification(1, "INFO", "To be read");
        var notification = await _context.Notifications.FirstAsync();

        await _service.MarkAsReadAsync(1, notification.NotificationId);

        var updated = await _context.Notifications.FindAsync(notification.NotificationId);
        updated!.IsRead.Should().Be("Y");
        updated.ReadAt.Should().NotBeNull();
    }

    // --- MarkAllAsReadAsync tests ---
    // Note: MarkAllAsReadAsync uses ExecuteUpdateAsync which is not supported
    // by the EF Core in-memory provider. This test verifies the exception is
    // thrown, confirming the method calls ExecuteUpdateAsync as expected.
    // Full integration tests against a real MySQL database would validate the behavior.

    [Fact]
    public async Task MarkAllAsReadAsync_UsesExecuteUpdate_NotSupportedByInMemory()
    {
        SeedNotification(1, "INFO", "Unread 1");
        SeedNotification(1, "ALERT", "Unread 2");

        var act = () => _service.MarkAllAsReadAsync(1);

        // ExecuteUpdateAsync is not supported by the in-memory provider
        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    // --- GetUnreadCountAsync tests ---

    [Fact]
    public async Task GetUnreadCountAsync_ReturnsCorrectCount()
    {
        SeedNotification(1, "INFO", "Unread 1");
        SeedNotification(1, "ALERT", "Unread 2");
        SeedNotification(1, "INFO", "Read", isRead: true);

        var count = await _service.GetUnreadCountAsync(1);

        count.Should().Be(2);
    }

    // --- CreateNotificationAsync tests ---

    [Fact]
    public async Task CreateNotificationAsync_CreatesNotification()
    {
        await _service.CreateNotificationAsync(
            userId: 1,
            type: "NEW_OPPORTUNITY",
            title: "New opportunity found",
            message: "A new WOSB opportunity was found.",
            entityType: "OPPORTUNITY",
            entityId: "NOTICE-001");

        var notification = await _context.Notifications.FirstOrDefaultAsync();
        notification.Should().NotBeNull();
        notification!.UserId.Should().Be(1);
        notification.NotificationType.Should().Be("NEW_OPPORTUNITY");
        notification.Title.Should().Be("New opportunity found");
        notification.Message.Should().Be("A new WOSB opportunity was found.");
        notification.EntityType.Should().Be("OPPORTUNITY");
        notification.EntityId.Should().Be("NOTICE-001");
        notification.IsRead.Should().Be("N");
    }
}
