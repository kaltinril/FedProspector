using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Exceptions;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class ProposalsControllerTests
{
    private readonly Mock<IProposalService> _serviceMock = new();
    private readonly ProposalsController _controller;

    public ProposalsControllerTests()
    {
        _controller = new ProposalsController(_serviceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    private static ClaimsPrincipal CreateUser(int userId = 1, string role = "user", bool isOrgAdmin = false, int orgId = 1)
    {
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, userId.ToString()),
            new(ClaimTypes.NameIdentifier, userId.ToString()),
            new(ClaimTypes.Role, role),
            new("is_org_admin", isOrgAdmin.ToString().ToLower()),
            new("org_id", orgId.ToString())
        };
        return new ClaimsPrincipal(new ClaimsIdentity(claims, "TestAuth"));
    }

    private void SetAuthenticatedUser(int userId = 1, int orgId = 1)
    {
        _controller.ControllerContext.HttpContext.User = CreateUser(userId, orgId: orgId);
    }

    // --- List ---

    [Fact]
    public async Task List_NoUser_ReturnsUnauthorized()
    {
        var request = new ProposalSearchRequest();

        var result = await _controller.List(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task List_AuthenticatedUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new ProposalSearchRequest();
        _serviceMock.Setup(s => s.ListAsync(10, request))
            .ReturnsAsync(new PagedResponse<ProposalDetailDto>());

        var result = await _controller.List(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task List_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 25);
        var request = new ProposalSearchRequest();
        _serviceMock.Setup(s => s.ListAsync(25, request))
            .ReturnsAsync(new PagedResponse<ProposalDetailDto>());

        await _controller.List(request);

        _serviceMock.Verify(s => s.ListAsync(25, request), Times.Once);
    }

    [Fact]
    public async Task List_ReturnsPaginatedResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new ProposalSearchRequest();
        var expected = new PagedResponse<ProposalDetailDto>
        {
            TotalCount = 5,
            Page = 1,
            PageSize = 25,
            Items = new List<ProposalDetailDto>
            {
                new() { ProposalId = 1, ProposalStatus = "DRAFT" },
                new() { ProposalId = 2, ProposalStatus = "IN_REVIEW" }
            }
        };
        _serviceMock.Setup(s => s.ListAsync(10, request)).ReturnsAsync(expected);

        var result = await _controller.List(request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task List_OrgScopedOnlyUsesClaimOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 50);
        var request = new ProposalSearchRequest();
        _serviceMock.Setup(s => s.ListAsync(50, request))
            .ReturnsAsync(new PagedResponse<ProposalDetailDto>());

        await _controller.List(request);

        // Verify the service is called with exactly the org_id from the claim
        _serviceMock.Verify(s => s.ListAsync(50, request), Times.Once);
        _serviceMock.Verify(s => s.ListAsync(It.Is<int>(id => id != 50), It.IsAny<ProposalSearchRequest>()), Times.Never);
    }

    // --- Create ---

    [Fact]
    public async Task Create_NoUser_ReturnsUnauthorized()
    {
        var request = new CreateProposalRequest();

        var result = await _controller.Create(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Create_AuthenticatedUser_Returns201()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new CreateProposalRequest { ProspectId = 5 };
        _serviceMock.Setup(s => s.CreateAsync(1, 10, request))
            .ReturnsAsync(new ProposalDetailDto { ProposalId = 100 });

        var result = await _controller.Create(request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(201);
    }

    [Fact]
    public async Task Create_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 3, orgId: 20);
        var request = new CreateProposalRequest { ProspectId = 7 };
        _serviceMock.Setup(s => s.CreateAsync(3, 20, request))
            .ReturnsAsync(new ProposalDetailDto());

        await _controller.Create(request);

        _serviceMock.Verify(s => s.CreateAsync(3, 20, request), Times.Once);
    }

    // --- CreateMilestone ---

    [Fact]
    public async Task CreateMilestone_NoUser_ReturnsUnauthorized()
    {
        var request = new CreateMilestoneRequest { Title = "Review Draft" };

        var result = await _controller.CreateMilestone(1, request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task CreateMilestone_AuthenticatedUser_Returns201()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new CreateMilestoneRequest { Title = "Finalize", DueDate = DateTime.UtcNow.AddDays(7) };
        _serviceMock.Setup(s => s.CreateMilestoneAsync(10, 5, 1, request))
            .ReturnsAsync(new ProposalMilestoneDto { MilestoneId = 50, MilestoneName = "Finalize" });

        var result = await _controller.CreateMilestone(5, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(201);
    }

    [Fact]
    public async Task CreateMilestone_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 2, orgId: 15);
        var request = new CreateMilestoneRequest { Title = "Submit" };
        _serviceMock.Setup(s => s.CreateMilestoneAsync(15, 8, 2, request))
            .ReturnsAsync(new ProposalMilestoneDto());

        await _controller.CreateMilestone(8, request);

        _serviceMock.Verify(s => s.CreateMilestoneAsync(15, 8, 2, request), Times.Once);
    }

    [Fact]
    public async Task CreateMilestone_ProposalNotFound_Returns404()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new CreateMilestoneRequest { Title = "Test" };
        _serviceMock.Setup(s => s.CreateMilestoneAsync(10, 999, 1, request))
            .ThrowsAsync(new KeyNotFoundException("Proposal not found"));

        var result = await _controller.CreateMilestone(999, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(404);
    }

    // --- Update ---

    [Fact]
    public async Task Update_NoUser_ReturnsUnauthorized()
    {
        var request = new UpdateProposalRequest();

        var result = await _controller.Update(1, request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Update_AuthenticatedUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateProposalRequest { EstimatedValue = 50000 };
        _serviceMock.Setup(s => s.UpdateAsync(10, 5, 1, request))
            .ReturnsAsync(new ProposalDetailDto { ProposalId = 5 });

        var result = await _controller.Update(5, request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Update_ProposalNotFound_Returns404()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateProposalRequest();
        _serviceMock.Setup(s => s.UpdateAsync(10, 999, 1, request))
            .ThrowsAsync(new KeyNotFoundException("Proposal not found"));

        var result = await _controller.Update(999, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(404);
    }

    [Fact]
    public async Task Update_Conflict_Returns409()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateProposalRequest();
        _serviceMock.Setup(s => s.UpdateAsync(10, 5, 1, request))
            .ThrowsAsync(new ConflictException("Concurrent update detected"));

        var result = await _controller.Update(5, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(409);
    }

    [Fact]
    public async Task Update_InvalidOperation_Returns400()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateProposalRequest();
        _serviceMock.Setup(s => s.UpdateAsync(10, 5, 1, request))
            .ThrowsAsync(new InvalidOperationException("Invalid status transition"));

        var result = await _controller.Update(5, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(400);
    }

    // --- GetMilestones ---

    [Fact]
    public async Task GetMilestones_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.GetMilestones(1);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetMilestones_AuthenticatedUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetMilestonesAsync(10, 5))
            .ReturnsAsync(new List<ProposalMilestoneDto>());

        var result = await _controller.GetMilestones(5);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetMilestones_ProposalNotFound_Returns404()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetMilestonesAsync(10, 999))
            .ThrowsAsync(new KeyNotFoundException("Proposal not found"));

        var result = await _controller.GetMilestones(999);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(404);
    }

    // --- AddMilestone returns DTO with 201 ---

    [Fact]
    public async Task AddMilestone_ReturnsMilestoneDto()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new CreateMilestoneRequest
        {
            Title = "Draft Review",
            DueDate = DateTime.UtcNow.AddDays(14)
        };
        var expected = new ProposalMilestoneDto
        {
            MilestoneId = 42,
            MilestoneName = "Draft Review",
            Status = "PENDING"
        };
        _serviceMock.Setup(s => s.CreateMilestoneAsync(10, 5, 1, request))
            .ReturnsAsync(expected);

        var result = await _controller.CreateMilestone(5, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(201);
        statusResult.Value.Should().Be(expected);
    }

    // --- UpdateMilestone returns updated DTO with 200 ---

    [Fact]
    public async Task UpdateMilestone_ReturnsUpdatedDto()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateMilestoneRequest { Status = "COMPLETED" };
        var expected = new ProposalMilestoneDto
        {
            MilestoneId = 42,
            MilestoneName = "Draft Review",
            Status = "COMPLETED"
        };
        _serviceMock.Setup(s => s.UpdateMilestoneAsync(10, 5, 42, 1, request))
            .ReturnsAsync(expected);

        var result = await _controller.UpdateMilestone(5, 42, request);

        result.Should().BeOfType<OkObjectResult>();
        var okResult = result as OkObjectResult;
        okResult!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task UpdateMilestone_NotFound_Returns404()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateMilestoneRequest { Status = "COMPLETED" };
        _serviceMock.Setup(s => s.UpdateMilestoneAsync(10, 5, 999, 1, request))
            .ThrowsAsync(new KeyNotFoundException("Milestone not found"));

        var result = await _controller.UpdateMilestone(5, 999, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(404);
    }

    [Fact]
    public async Task UpdateMilestone_NoUser_ReturnsUnauthorized()
    {
        var request = new UpdateMilestoneRequest { Status = "COMPLETED" };

        var result = await _controller.UpdateMilestone(5, 42, request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    // --- AddDocument returns DTO with 201 ---

    [Fact]
    public async Task AddDocument_ReturnsDocumentDto()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new AddProposalDocumentRequest
        {
            FileName = "proposal_v1.pdf",
            DocumentType = "PROPOSAL"
        };
        var expected = new ProposalDocumentDto
        {
            DocumentId = 99,
            FileName = "proposal_v1.pdf",
            DocumentType = "PROPOSAL"
        };
        _serviceMock.Setup(s => s.AddDocumentAsync(10, 5, 1, request))
            .ReturnsAsync(expected);

        var result = await _controller.AddDocument(5, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(201);
        statusResult.Value.Should().Be(expected);
    }

    [Fact]
    public async Task AddDocument_ProposalNotFound_Returns404()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new AddProposalDocumentRequest
        {
            FileName = "test.pdf",
            DocumentType = "PROPOSAL"
        };
        _serviceMock.Setup(s => s.AddDocumentAsync(10, 999, 1, request))
            .ThrowsAsync(new KeyNotFoundException("Proposal not found"));

        var result = await _controller.AddDocument(999, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(404);
    }

    [Fact]
    public async Task AddDocument_NoUser_ReturnsUnauthorized()
    {
        var request = new AddProposalDocumentRequest
        {
            FileName = "test.pdf",
            DocumentType = "PROPOSAL"
        };

        var result = await _controller.AddDocument(5, request);

        result.Should().BeOfType<UnauthorizedResult>();
    }
}
