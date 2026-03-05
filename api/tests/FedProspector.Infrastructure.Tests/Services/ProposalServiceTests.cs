using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;

namespace FedProspector.Infrastructure.Tests.Services;

public class ProposalServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly ProposalService _service;
    private readonly Mock<IActivityLogService> _activityLogMock;
    private readonly Mock<INotificationService> _notificationMock;

    public ProposalServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);

        _activityLogMock = new Mock<IActivityLogService>();
        _notificationMock = new Mock<INotificationService>();

        _service = new ProposalService(
            _context,
            _activityLogMock.Object,
            _notificationMock.Object,
            NullLogger<ProposalService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    // -----------------------------------------------------------------------
    // Seed Helpers
    // -----------------------------------------------------------------------

    private Prospect SeedProspectWithOpportunity(
        int organizationId = 1,
        string noticeId = "NOTICE-001",
        string status = "PURSUING")
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = $"Opportunity {noticeId}",
            Active = "Y"
        });

        var prospect = new Prospect
        {
            OrganizationId = organizationId,
            NoticeId = noticeId,
            Status = status,
            Priority = "MEDIUM",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        _context.Prospects.Add(prospect);
        _context.SaveChanges();
        return prospect;
    }

    private Proposal SeedProposal(int prospectId, string status = "DRAFT", decimal? estimatedValue = null)
    {
        var proposal = new Proposal
        {
            ProspectId = prospectId,
            ProposalStatus = status,
            EstimatedValue = estimatedValue,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        _context.Proposals.Add(proposal);
        _context.SaveChanges();
        return proposal;
    }

    private ProposalMilestone SeedMilestone(int proposalId, string name = "Draft Due", string status = "PENDING")
    {
        var milestone = new ProposalMilestone
        {
            ProposalId = proposalId,
            MilestoneName = name,
            Status = status,
            CreatedAt = DateTime.UtcNow
        };
        _context.ProposalMilestones.Add(milestone);
        _context.SaveChanges();
        return milestone;
    }

    // -----------------------------------------------------------------------
    // CreateAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task CreateAsync_ValidRequest_CreatesProposal()
    {
        var prospect = SeedProspectWithOpportunity();

        var request = new CreateProposalRequest
        {
            ProspectId = prospect.ProspectId,
            SubmissionDeadline = DateTime.UtcNow.AddDays(30),
            EstimatedValue = 500_000m
        };

        var result = await _service.CreateAsync(userId: 1, organizationId: 1, request);

        result.Should().NotBeNull();
        result.ProspectId.Should().Be(prospect.ProspectId);
        result.ProposalStatus.Should().Be("DRAFT");
        result.EstimatedValue.Should().Be(500_000m);
        // Default milestones should be created
        result.Milestones.Should().HaveCount(5);
    }

    [Fact]
    public async Task CreateAsync_DuplicateProposal_Throws()
    {
        var prospect = SeedProspectWithOpportunity();
        SeedProposal(prospect.ProspectId);

        var request = new CreateProposalRequest { ProspectId = prospect.ProspectId };

        var act = () => _service.CreateAsync(userId: 1, organizationId: 1, request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*already exists*");
    }

    [Fact]
    public async Task CreateAsync_WrongOrg_Throws()
    {
        var prospect = SeedProspectWithOpportunity(organizationId: 1);

        var request = new CreateProposalRequest { ProspectId = prospect.ProspectId };

        // Try to create in org 2 -- prospect belongs to org 1
        var act = () => _service.CreateAsync(userId: 1, organizationId: 2, request);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*not found*");
    }

    // -----------------------------------------------------------------------
    // UpdateAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task UpdateAsync_ValidRequest_UpdatesProposal()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId);

        var request = new UpdateProposalRequest
        {
            EstimatedValue = 750_000m,
            WinProbabilityPct = 65.0m,
            LessonsLearned = "Focus on past performance"
        };

        var result = await _service.UpdateAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId,
            userId: 1,
            request);

        result.EstimatedValue.Should().Be(750_000m);
        result.WinProbabilityPct.Should().Be(65.0m);
        result.LessonsLearned.Should().Be("Focus on past performance");
    }

    [Fact]
    public async Task UpdateAsync_WrongOrg_Throws()
    {
        // CRITICAL: multi-tenancy test
        var prospect = SeedProspectWithOpportunity(organizationId: 1);
        var proposal = SeedProposal(prospect.ProspectId);

        var request = new UpdateProposalRequest { EstimatedValue = 100_000m };

        // Try to update from org 2
        var act = () => _service.UpdateAsync(
            organizationId: 2,
            proposalId: proposal.ProposalId,
            userId: 1,
            request);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*not found*");
    }

    [Fact]
    public async Task UpdateAsync_ValidStatusTransition_UpdatesStatus()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId, status: "DRAFT");

        var request = new UpdateProposalRequest { Status = "IN_REVIEW" };

        var result = await _service.UpdateAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId,
            userId: 1,
            request);

        result.ProposalStatus.Should().Be("IN_REVIEW");
    }

    [Fact]
    public async Task UpdateAsync_InvalidStatusTransition_Throws()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId, status: "DRAFT");

        var request = new UpdateProposalRequest { Status = "AWARDED" };

        var act = () => _service.UpdateAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId,
            userId: 1,
            request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*Invalid proposal status transition*");
    }

    [Fact]
    public async Task UpdateAsync_TerminalStatus_Throws()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId, status: "AWARDED");

        var request = new UpdateProposalRequest { Status = "DRAFT" };

        var act = () => _service.UpdateAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId,
            userId: 1,
            request);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*terminal status*");
    }

    // -----------------------------------------------------------------------
    // AddDocumentAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task AddDocumentAsync_ValidRequest_AddsDocument()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId);

        var request = new AddProposalDocumentRequest
        {
            FileName = "technical_volume.pdf",
            DocumentType = "TECHNICAL",
            FileSizeBytes = 1_048_576,
            Notes = "First draft"
        };

        var result = await _service.AddDocumentAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId,
            userId: 1,
            request);

        result.FileName.Should().Be("technical_volume.pdf");
        result.DocumentType.Should().Be("TECHNICAL");
        result.FileSizeBytes.Should().Be(1_048_576);
        result.Notes.Should().Be("First draft");
        result.DocumentId.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task AddDocumentAsync_WrongOrg_Throws()
    {
        var prospect = SeedProspectWithOpportunity(organizationId: 1);
        var proposal = SeedProposal(prospect.ProspectId);

        var request = new AddProposalDocumentRequest
        {
            FileName = "test.pdf",
            DocumentType = "TECHNICAL"
        };

        var act = () => _service.AddDocumentAsync(
            organizationId: 2,
            proposalId: proposal.ProposalId,
            userId: 1,
            request);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*not found*");
    }

    // -----------------------------------------------------------------------
    // GetMilestonesAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetMilestonesAsync_ReturnsMilestones()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId);
        SeedMilestone(proposal.ProposalId, "Draft Due");
        SeedMilestone(proposal.ProposalId, "Internal Review");
        SeedMilestone(proposal.ProposalId, "Final Submission");

        var result = await _service.GetMilestonesAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId);

        result.Should().HaveCount(3);
    }

    [Fact]
    public async Task GetMilestonesAsync_WrongOrg_Throws()
    {
        var prospect = SeedProspectWithOpportunity(organizationId: 1);
        var proposal = SeedProposal(prospect.ProspectId);

        var act = () => _service.GetMilestonesAsync(
            organizationId: 2,
            proposalId: proposal.ProposalId);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*not found*");
    }

    // -----------------------------------------------------------------------
    // CreateMilestoneAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task CreateMilestoneAsync_ValidRequest_CreatesMilestone()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId);

        var request = new CreateMilestoneRequest
        {
            Title = "Custom Milestone",
            DueDate = DateTime.UtcNow.AddDays(14),
            AssignedTo = null
        };

        var result = await _service.CreateMilestoneAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId,
            userId: 1,
            request);

        result.MilestoneName.Should().Be("Custom Milestone");
        result.Status.Should().Be("PENDING");
        result.MilestoneId.Should().BeGreaterThan(0);
    }

    // -----------------------------------------------------------------------
    // UpdateMilestoneAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task UpdateMilestoneAsync_ValidRequest_UpdatesMilestone()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId);
        var milestone = SeedMilestone(proposal.ProposalId, "Draft Due");

        var request = new UpdateMilestoneRequest
        {
            Status = "COMPLETE",
            CompletedDate = DateOnly.FromDateTime(DateTime.UtcNow),
            Notes = "Completed on time"
        };

        var result = await _service.UpdateMilestoneAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId,
            milestoneId: milestone.MilestoneId,
            userId: 1,
            request);

        result.Status.Should().Be("COMPLETE");
        result.CompletedDate.Should().NotBeNull();
        result.Notes.Should().Be("Completed on time");
    }

    [Fact]
    public async Task UpdateMilestoneAsync_NonexistentMilestone_Throws()
    {
        var prospect = SeedProspectWithOpportunity();
        var proposal = SeedProposal(prospect.ProspectId);

        var request = new UpdateMilestoneRequest { Status = "COMPLETE" };

        var act = () => _service.UpdateMilestoneAsync(
            organizationId: 1,
            proposalId: proposal.ProposalId,
            milestoneId: 999,
            userId: 1,
            request);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*Milestone*not found*");
    }

    // -----------------------------------------------------------------------
    // ListAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task ListAsync_FiltersByOrganization()
    {
        // CRITICAL: multi-tenancy test
        var prospect1 = SeedProspectWithOpportunity(organizationId: 1, noticeId: "NOTICE-ORG1");
        SeedProposal(prospect1.ProspectId);

        var prospect2 = SeedProspectWithOpportunity(organizationId: 2, noticeId: "NOTICE-ORG2");
        SeedProposal(prospect2.ProspectId);

        var request = new ProposalSearchRequest();

        var result = await _service.ListAsync(organizationId: 1, request);

        result.TotalCount.Should().Be(1);
    }

    [Fact]
    public async Task ListAsync_FiltersByStatus()
    {
        var prospect1 = SeedProspectWithOpportunity(noticeId: "NOTICE-001");
        SeedProposal(prospect1.ProspectId, status: "DRAFT");

        var prospect2 = SeedProspectWithOpportunity(noticeId: "NOTICE-002");
        SeedProposal(prospect2.ProspectId, status: "IN_REVIEW");

        var request = new ProposalSearchRequest { Status = "DRAFT" };

        var result = await _service.ListAsync(organizationId: 1, request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(p => p.ProposalStatus == "DRAFT");
    }

    [Fact]
    public async Task ListAsync_PaginatesCorrectly()
    {
        for (int i = 1; i <= 5; i++)
        {
            var prospect = SeedProspectWithOpportunity(noticeId: $"NOTICE-{i:D3}");
            SeedProposal(prospect.ProspectId);
        }

        var request = new ProposalSearchRequest
        {
            Page = 1,
            PageSize = 2
        };

        var result = await _service.ListAsync(organizationId: 1, request);

        result.TotalCount.Should().Be(5);
        result.Items.Count().Should().Be(2);
        result.HasNextPage.Should().BeTrue();
    }
}
