using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;

namespace FedProspector.Infrastructure.Tests.Services;

public class ProspectServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly ProspectService _service;
    private readonly Mock<IGoNoGoScoringService> _scoringServiceMock;
    private readonly Mock<IActivityLogService> _activityLogMock;
    private readonly Mock<INotificationService> _notificationMock;

    public ProspectServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);

        _scoringServiceMock = new Mock<IGoNoGoScoringService>();
        _activityLogMock = new Mock<IActivityLogService>();
        _notificationMock = new Mock<INotificationService>();

        _service = new ProspectService(
            _context,
            _scoringServiceMock.Object,
            _activityLogMock.Object,
            _notificationMock.Object,
            NullLogger<ProspectService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    // -----------------------------------------------------------------------
    // Seed Helpers
    // -----------------------------------------------------------------------

    private void SeedOpportunity(string noticeId = "NOTICE-001", string? setAsideCode = null, string? naicsCode = null)
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = $"Test Opportunity {noticeId}",
            SetAsideCode = setAsideCode,
            NaicsCode = naicsCode,
            Active = "Y"
        });
        _context.SaveChanges();
    }

    private Prospect SeedProspect(
        int organizationId = 1,
        string noticeId = "NOTICE-001",
        string status = "NEW",
        int? assignedTo = null,
        int prospectId = 0)
    {
        var prospect = new Prospect
        {
            OrganizationId = organizationId,
            NoticeId = noticeId,
            Status = status,
            AssignedTo = assignedTo,
            Priority = "MEDIUM",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        if (prospectId > 0)
            prospect.ProspectId = prospectId;

        _context.Prospects.Add(prospect);
        _context.SaveChanges();
        return prospect;
    }

    private AppUser SeedUser(int organizationId = 1, string username = "testuser", string isActive = "Y")
    {
        var user = new AppUser
        {
            OrganizationId = organizationId,
            Username = username,
            DisplayName = $"Test User ({username})",
            IsActive = isActive,
            IsAdmin = "N",
            MfaEnabled = "N",
            OrgRole = "member",
            ForcePasswordChange = "N"
        };
        _context.AppUsers.Add(user);
        _context.SaveChanges();
        return user;
    }

    private void SeedTeamMember(int prospectId, string? ueiSam = "UEI000000001", string role = "PRIME")
    {
        _context.ProspectTeamMembers.Add(new ProspectTeamMember
        {
            ProspectId = prospectId,
            UeiSam = ueiSam,
            Role = role
        });
        _context.SaveChanges();
    }

    // -----------------------------------------------------------------------
    // CreateAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task CreateAsync_ValidRequest_CreatesProspect()
    {
        SeedOpportunity("NOTICE-001");
        var user = SeedUser();

        var request = new CreateProspectRequest
        {
            NoticeId = "NOTICE-001",
            Priority = "HIGH",
            Notes = "Initial notes"
        };

        var result = await _service.CreateAsync(user.UserId, 1, request);

        result.Should().NotBeNull();
        result.Prospect.NoticeId.Should().Be("NOTICE-001");
        result.Prospect.Status.Should().Be("NEW");
        result.Prospect.Priority.Should().Be("HIGH");
        result.Notes.Should().NotBeEmpty();
        result.Notes.First().NoteText.Should().Contain("Initial notes");
    }

    [Fact]
    public async Task CreateAsync_DuplicateNoticeId_Throws()
    {
        SeedOpportunity("NOTICE-001");
        SeedProspect(organizationId: 1, noticeId: "NOTICE-001");
        var user = SeedUser();

        var request = new CreateProspectRequest { NoticeId = "NOTICE-001" };

        var act = () => _service.CreateAsync(user.UserId, 1, request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*already exists*");
    }

    // -----------------------------------------------------------------------
    // SearchAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task SearchAsync_FiltersByOrganization()
    {
        // CRITICAL: multi-tenancy test
        SeedOpportunity("NOTICE-ORG1");
        SeedOpportunity("NOTICE-ORG2");
        SeedProspect(organizationId: 1, noticeId: "NOTICE-ORG1");
        SeedProspect(organizationId: 2, noticeId: "NOTICE-ORG2");

        var request = new ProspectSearchRequest { OpenOnly = false };

        var result = await _service.SearchAsync(1, request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(p => p.NoticeId == "NOTICE-ORG1");
    }

    [Fact]
    public async Task SearchAsync_PaginatesCorrectly()
    {
        // Seed 5 prospects for org 1
        for (int i = 1; i <= 5; i++)
        {
            var noticeId = $"NOTICE-{i:D3}";
            SeedOpportunity(noticeId);
            SeedProspect(organizationId: 1, noticeId: noticeId);
        }

        var request = new ProspectSearchRequest
        {
            Page = 1,
            PageSize = 2,
            OpenOnly = false
        };

        var result = await _service.SearchAsync(1, request);

        result.TotalCount.Should().Be(5);
        result.Items.Count().Should().Be(2);
        result.Page.Should().Be(1);
        result.PageSize.Should().Be(2);
        result.HasNextPage.Should().BeTrue();
    }

    // -----------------------------------------------------------------------
    // GetDetailAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetDetailAsync_WrongOrg_ReturnsNull()
    {
        // CRITICAL: multi-tenancy test
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001");

        var result = await _service.GetDetailAsync(2, prospect.ProspectId);

        result.Should().BeNull();
    }

    // -----------------------------------------------------------------------
    // UpdateStatusAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task UpdateStatusAsync_ValidTransition_UpdatesStatus()
    {
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001", status: "NEW");
        var user = SeedUser();

        var request = new UpdateProspectStatusRequest
        {
            NewStatus = "REVIEWING",
            Notes = "Looks promising"
        };

        var result = await _service.UpdateStatusAsync(1, prospect.ProspectId, user.UserId, request);

        result.Prospect.Status.Should().Be("REVIEWING");
    }

    [Fact]
    public async Task UpdateStatusAsync_InvalidTransition_Throws()
    {
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001", status: "NEW");
        var user = SeedUser();

        var request = new UpdateProspectStatusRequest { NewStatus = "WON" };

        var act = () => _service.UpdateStatusAsync(1, prospect.ProspectId, user.UserId, request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*Invalid status transition*");
    }

    [Fact]
    public async Task UpdateStatusAsync_TerminalStatus_Throws()
    {
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001", status: "WON");
        var user = SeedUser();

        var request = new UpdateProspectStatusRequest { NewStatus = "REVIEWING" };

        var act = () => _service.UpdateStatusAsync(1, prospect.ProspectId, user.UserId, request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*terminal status*");
    }

    // -----------------------------------------------------------------------
    // AddNoteAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task AddNoteAsync_ValidRequest_CreatesNote()
    {
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001");
        var user = SeedUser();

        var request = new CreateProspectNoteRequest
        {
            NoteType = "COMMENT",
            NoteText = "This is a test note"
        };

        var result = await _service.AddNoteAsync(1, prospect.ProspectId, user.UserId, request);

        result.NoteType.Should().Be("COMMENT");
        result.NoteText.Should().Be("This is a test note");
        result.NoteId.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task AddNoteAsync_StatusChangeType_Throws()
    {
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001");
        var user = SeedUser();

        var request = new CreateProspectNoteRequest
        {
            NoteType = "STATUS_CHANGE",
            NoteText = "Trying to fake a status change"
        };

        var act = () => _service.AddNoteAsync(1, prospect.ProspectId, user.UserId, request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*STATUS_CHANGE*system-generated*");
    }

    // -----------------------------------------------------------------------
    // AddTeamMemberAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task AddTeamMemberAsync_ValidRequest_AddsMember()
    {
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001");
        var user = SeedUser();

        var request = new AddTeamMemberRequest
        {
            UeiSam = "UEI000000001",
            Role = "SUBCONTRACTOR",
            CommitmentPct = 25.0m
        };

        var result = await _service.AddTeamMemberAsync(1, prospect.ProspectId, user.UserId, request);

        result.UeiSam.Should().Be("UEI000000001");
        result.Role.Should().Be("SUBCONTRACTOR");
        result.CommitmentPct.Should().Be(25.0m);
        result.Id.Should().BeGreaterThan(0);
    }

    // -----------------------------------------------------------------------
    // RemoveTeamMemberAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task RemoveTeamMemberAsync_ExistingMember_ReturnsTrue()
    {
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001");
        SeedTeamMember(prospect.ProspectId);
        var user = SeedUser();

        var member = await _context.ProspectTeamMembers.FirstAsync();

        var result = await _service.RemoveTeamMemberAsync(1, prospect.ProspectId, member.Id, user.UserId);

        result.Should().BeTrue();
        (await _context.ProspectTeamMembers.CountAsync()).Should().Be(0);
    }

    [Fact]
    public async Task RemoveTeamMemberAsync_WrongOrg_ReturnsFalse()
    {
        SeedOpportunity("NOTICE-001");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001");
        SeedTeamMember(prospect.ProspectId);
        var user = SeedUser();

        var member = await _context.ProspectTeamMembers.FirstAsync();

        // Try to remove with wrong org
        var result = await _service.RemoveTeamMemberAsync(999, prospect.ProspectId, member.Id, user.UserId);

        result.Should().BeFalse();
    }

    // -----------------------------------------------------------------------
    // ReassignAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task ReassignAsync_ValidRequest_UpdatesAssignee()
    {
        SeedOpportunity("NOTICE-001");
        var originalUser = SeedUser(organizationId: 1, username: "original");
        var newUser = SeedUser(organizationId: 1, username: "newuser");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001", assignedTo: originalUser.UserId);

        var request = new ReassignProspectRequest
        {
            NewAssignedTo = newUser.UserId,
            Notes = "Reassigning for coverage"
        };

        var result = await _service.ReassignAsync(1, prospect.ProspectId, originalUser.UserId, request);

        result.Prospect.AssignedTo.Should().NotBeNull();
        result.Prospect.AssignedTo!.UserId.Should().Be(newUser.UserId);
    }

    [Fact]
    public async Task ReassignAsync_InactiveUser_Throws()
    {
        SeedOpportunity("NOTICE-001");
        var originalUser = SeedUser(organizationId: 1, username: "original");
        var inactiveUser = SeedUser(organizationId: 1, username: "inactive", isActive: "N");
        var prospect = SeedProspect(organizationId: 1, noticeId: "NOTICE-001", assignedTo: originalUser.UserId);

        var request = new ReassignProspectRequest { NewAssignedTo = inactiveUser.UserId };

        var act = () => _service.ReassignAsync(1, prospect.ProspectId, originalUser.UserId, request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*not active*");
    }
}
