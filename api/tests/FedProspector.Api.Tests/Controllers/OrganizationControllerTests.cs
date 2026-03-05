using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class OrganizationControllerTests
{
    private readonly Mock<IOrganizationService> _serviceMock = new();
    private readonly Mock<ICompanyProfileService> _profileServiceMock = new();
    private readonly OrganizationController _controller;

    public OrganizationControllerTests()
    {
        _controller = new OrganizationController(_serviceMock.Object, _profileServiceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    private static ClaimsPrincipal CreateUser(int userId = 1, string role = "user", bool isAdmin = false, int orgId = 1, string orgRole = "member")
    {
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, userId.ToString()),
            new(ClaimTypes.NameIdentifier, userId.ToString()),
            new(ClaimTypes.Role, role),
            new("is_admin", isAdmin.ToString().ToLower()),
            new("org_id", orgId.ToString()),
            new("org_role", orgRole)
        };
        return new ClaimsPrincipal(new ClaimsIdentity(claims, "TestAuth"));
    }

    private void SetAuthenticatedUser(int userId = 1, int orgId = 1, string orgRole = "member")
    {
        _controller.ControllerContext.HttpContext.User = CreateUser(userId, orgId: orgId, orgRole: orgRole);
    }

    // --- GetOrganization ---

    [Fact]
    public async Task GetOrganization_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.GetOrganization();

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetOrganization_AuthenticatedUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetOrganizationAsync(10))
            .ReturnsAsync(new OrganizationDto { Id = 10, Name = "Test Org" });

        var result = await _controller.GetOrganization();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetOrganization_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 42);
        _serviceMock.Setup(s => s.GetOrganizationAsync(42))
            .ReturnsAsync(new OrganizationDto { Id = 42 });

        await _controller.GetOrganization();

        _serviceMock.Verify(s => s.GetOrganizationAsync(42), Times.Once);
    }

    [Fact]
    public async Task GetOrganization_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var expected = new OrganizationDto { Id = 10, Name = "Acme Corp", Slug = "acme" };
        _serviceMock.Setup(s => s.GetOrganizationAsync(10)).ReturnsAsync(expected);

        var result = await _controller.GetOrganization() as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task GetOrganization_OrgNotFound_ThrowsKeyNotFound()
    {
        SetAuthenticatedUser(userId: 1, orgId: 999);
        _serviceMock.Setup(s => s.GetOrganizationAsync(999))
            .ThrowsAsync(new KeyNotFoundException("Organization 999 not found."));

        var act = () => _controller.GetOrganization();

        await act.Should().ThrowAsync<KeyNotFoundException>();
    }

    // --- UpdateOrganization ---

    [Fact]
    public async Task UpdateOrganization_NoUser_ReturnsUnauthorized()
    {
        var request = new UpdateOrganizationRequest { Name = "New Name" };

        var result = await _controller.UpdateOrganization(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task UpdateOrganization_AuthenticatedOrgAdmin_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        var request = new UpdateOrganizationRequest { Name = "Updated Org" };
        _serviceMock.Setup(s => s.UpdateOrganizationAsync(10, "Updated Org"))
            .ReturnsAsync(new OrganizationDto { Id = 10, Name = "Updated Org" });

        var result = await _controller.UpdateOrganization(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task UpdateOrganization_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 1, orgId: 15, orgRole: "admin");
        var request = new UpdateOrganizationRequest { Name = "New Name" };
        _serviceMock.Setup(s => s.UpdateOrganizationAsync(15, "New Name"))
            .ReturnsAsync(new OrganizationDto());

        await _controller.UpdateOrganization(request);

        _serviceMock.Verify(s => s.UpdateOrganizationAsync(15, "New Name"), Times.Once);
    }

    [Fact]
    public async Task UpdateOrganization_OrgNotFound_ThrowsKeyNotFound()
    {
        SetAuthenticatedUser(userId: 1, orgId: 999, orgRole: "admin");
        var request = new UpdateOrganizationRequest { Name = "Test" };
        _serviceMock.Setup(s => s.UpdateOrganizationAsync(999, "Test"))
            .ThrowsAsync(new KeyNotFoundException("Organization 999 not found."));

        var act = () => _controller.UpdateOrganization(request);

        await act.Should().ThrowAsync<KeyNotFoundException>();
    }

    // --- GetMembers ---

    [Fact]
    public async Task GetMembers_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.GetMembers();

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetMembers_AuthenticatedUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetMembersAsync(10))
            .ReturnsAsync(new List<OrganizationMemberDto>());

        var result = await _controller.GetMembers();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetMembers_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 25);
        _serviceMock.Setup(s => s.GetMembersAsync(25))
            .ReturnsAsync(new List<OrganizationMemberDto>());

        await _controller.GetMembers();

        _serviceMock.Verify(s => s.GetMembersAsync(25), Times.Once);
    }

    [Fact]
    public async Task GetMembers_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var expected = new List<OrganizationMemberDto>
        {
            new() { UserId = 1, Email = "alice@test.com", OrgRole = "admin" },
            new() { UserId = 2, Email = "bob@test.com", OrgRole = "member" }
        };
        _serviceMock.Setup(s => s.GetMembersAsync(10)).ReturnsAsync(expected);

        var result = await _controller.GetMembers() as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    // --- CreateInvite ---

    [Fact]
    public async Task CreateInvite_NoUser_ReturnsUnauthorized()
    {
        var request = new CreateInviteRequest { Email = "new@test.com" };

        var result = await _controller.CreateInvite(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task CreateInvite_AuthenticatedOrgAdmin_Returns201()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        var request = new CreateInviteRequest { Email = "new@test.com", OrgRole = "member" };
        _serviceMock.Setup(s => s.CreateInviteAsync(10, "new@test.com", "member", 1))
            .ReturnsAsync(new InviteDto { InviteId = 5, Email = "new@test.com" });

        var result = await _controller.CreateInvite(request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(201);
    }

    [Fact]
    public async Task CreateInvite_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 3, orgId: 20, orgRole: "admin");
        var request = new CreateInviteRequest { Email = "invite@test.com", OrgRole = "admin" };
        _serviceMock.Setup(s => s.CreateInviteAsync(20, "invite@test.com", "admin", 3))
            .ReturnsAsync(new InviteDto());

        await _controller.CreateInvite(request);

        _serviceMock.Verify(s => s.CreateInviteAsync(20, "invite@test.com", "admin", 3), Times.Once);
    }

    [Fact]
    public async Task CreateInvite_DuplicateEmail_ThrowsInvalidOperation()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        var request = new CreateInviteRequest { Email = "existing@test.com", OrgRole = "member" };
        _serviceMock.Setup(s => s.CreateInviteAsync(10, "existing@test.com", "member", 1))
            .ThrowsAsync(new InvalidOperationException("A pending invite already exists for this email."));

        var act = () => _controller.CreateInvite(request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("A pending invite already exists for this email.");
    }

    [Fact]
    public async Task CreateInvite_AlreadyMember_ThrowsInvalidOperation()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        var request = new CreateInviteRequest { Email = "member@test.com", OrgRole = "member" };
        _serviceMock.Setup(s => s.CreateInviteAsync(10, "member@test.com", "member", 1))
            .ThrowsAsync(new InvalidOperationException("This email is already a member of the organization."));

        var act = () => _controller.CreateInvite(request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("This email is already a member of the organization.");
    }

    [Fact]
    public async Task CreateInvite_MaxUsersReached_ThrowsInvalidOperation()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        var request = new CreateInviteRequest { Email = "new@test.com", OrgRole = "member" };
        _serviceMock.Setup(s => s.CreateInviteAsync(10, "new@test.com", "member", 1))
            .ThrowsAsync(new InvalidOperationException("Organization has reached its maximum user limit (10)."));

        var act = () => _controller.CreateInvite(request);

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    // --- GetPendingInvites ---

    [Fact]
    public async Task GetPendingInvites_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.GetPendingInvites();

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetPendingInvites_AuthenticatedOrgAdmin_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        _serviceMock.Setup(s => s.GetPendingInvitesAsync(10))
            .ReturnsAsync(new List<InviteDto>());

        var result = await _controller.GetPendingInvites();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetPendingInvites_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 30, orgRole: "admin");
        _serviceMock.Setup(s => s.GetPendingInvitesAsync(30))
            .ReturnsAsync(new List<InviteDto>());

        await _controller.GetPendingInvites();

        _serviceMock.Verify(s => s.GetPendingInvitesAsync(30), Times.Once);
    }

    [Fact]
    public async Task GetPendingInvites_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        var expected = new List<InviteDto>
        {
            new() { InviteId = 1, Email = "pending@test.com", OrgRole = "member" }
        };
        _serviceMock.Setup(s => s.GetPendingInvitesAsync(10)).ReturnsAsync(expected);

        var result = await _controller.GetPendingInvites() as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    // --- RevokeInvite ---

    [Fact]
    public async Task RevokeInvite_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.RevokeInvite(1);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task RevokeInvite_AuthenticatedOrgAdmin_ReturnsNoContent()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        _serviceMock.Setup(s => s.RevokeInviteAsync(10, 5))
            .Returns(Task.CompletedTask);

        var result = await _controller.RevokeInvite(5);

        result.Should().BeOfType<NoContentResult>();
    }

    [Fact]
    public async Task RevokeInvite_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 1, orgId: 20, orgRole: "admin");
        _serviceMock.Setup(s => s.RevokeInviteAsync(20, 8))
            .Returns(Task.CompletedTask);

        await _controller.RevokeInvite(8);

        _serviceMock.Verify(s => s.RevokeInviteAsync(20, 8), Times.Once);
    }

    [Fact]
    public async Task RevokeInvite_InviteNotFound_ThrowsKeyNotFound()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        _serviceMock.Setup(s => s.RevokeInviteAsync(10, 999))
            .ThrowsAsync(new KeyNotFoundException("Invite 999 not found in organization 10."));

        var act = () => _controller.RevokeInvite(999);

        await act.Should().ThrowAsync<KeyNotFoundException>();
    }

    [Fact]
    public async Task RevokeInvite_AlreadyAccepted_ThrowsInvalidOperation()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10, orgRole: "admin");
        _serviceMock.Setup(s => s.RevokeInviteAsync(10, 3))
            .ThrowsAsync(new InvalidOperationException("Cannot revoke an already accepted invite."));

        var act = () => _controller.RevokeInvite(3);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("Cannot revoke an already accepted invite.");
    }
}
