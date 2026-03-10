using System.Security.Cryptography;
using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class OrganizationService : IOrganizationService
{
    private readonly FedProspectorDbContext _context;
    private readonly IAuthService _authService;
    private readonly IActivityLogService _activityLogService;
    private readonly ILogger<OrganizationService> _logger;

    public OrganizationService(
        FedProspectorDbContext context,
        IAuthService authService,
        IActivityLogService activityLogService,
        ILogger<OrganizationService> logger)
    {
        _context = context;
        _authService = authService;
        _activityLogService = activityLogService;
        _logger = logger;
    }

    public async Task<OrganizationDto> GetOrganizationAsync(int orgId)
    {
        var org = await _context.Organizations
            .AsNoTracking()
            .FirstOrDefaultAsync(o => o.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found.");

        return MapToDto(org);
    }

    public async Task<OrganizationDto> UpdateOrganizationAsync(int orgId, string name)
    {
        var org = await _context.Organizations.FindAsync(orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found.");

        org.Name = name;
        org.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        _logger.LogInformation("Organization {OrgId} name updated to {Name}", orgId, name);

        return MapToDto(org);
    }

    public async Task<List<OrganizationMemberDto>> GetMembersAsync(int orgId)
    {
        // Verify org exists
        var orgExists = await _context.Organizations.AnyAsync(o => o.OrganizationId == orgId);
        if (!orgExists) throw new KeyNotFoundException($"Organization {orgId} not found.");

        return await _context.AppUsers
            .AsNoTracking()
            .Where(u => u.OrganizationId == orgId)
            .OrderBy(u => u.DisplayName)
            .Select(u => new OrganizationMemberDto
            {
                UserId = u.UserId,
                Email = u.Email,
                DisplayName = u.DisplayName,
                OrgRole = u.OrgRole,
                IsActive = u.IsActive == "Y",
                CreatedAt = u.CreatedAt
            })
            .ToListAsync();
    }

    public async Task<InviteDto> CreateInviteAsync(int orgId, string email, string orgRole, int invitedBy)
    {
        // Verify org exists
        var org = await _context.Organizations.FindAsync(orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found.");

        // Check if email already has a pending invite for this org
        var existingInvite = await _context.OrganizationInvites
            .AnyAsync(i => i.OrganizationId == orgId
                        && i.Email.ToLower() == email.ToLower()
                        && i.AcceptedAt == null
                        && i.ExpiresAt > DateTime.UtcNow);

        if (existingInvite)
        {
            throw new InvalidOperationException("A pending invite already exists for this email.");
        }

        // Check if email is already a member of this org
        var alreadyMember = await _context.AppUsers
            .AnyAsync(u => u.OrganizationId == orgId
                        && u.Email != null
                        && u.Email.ToLower() == email.ToLower());

        if (alreadyMember)
        {
            throw new InvalidOperationException("This email is already a member of the organization.");
        }

        // Check max users limit
        var currentUserCount = await _context.AppUsers
            .CountAsync(u => u.OrganizationId == orgId && u.IsActive == "Y");

        if (currentUserCount >= org.MaxUsers)
        {
            throw new InvalidOperationException($"Organization has reached its maximum user limit ({org.MaxUsers}).");
        }

        // Generate unique invite code
        var inviteCode = GenerateInviteCode();

        var invite = new OrganizationInvite
        {
            OrganizationId = orgId,
            Email = email,
            InviteCode = inviteCode,
            OrgRole = orgRole,
            InvitedBy = invitedBy,
            ExpiresAt = DateTime.UtcNow.AddDays(7),
            CreatedAt = DateTime.UtcNow
        };

        _context.OrganizationInvites.Add(invite);
        await _context.SaveChangesAsync();

        // Get inviter name for the DTO
        var inviterName = await _context.AppUsers
            .Where(u => u.UserId == invitedBy)
            .Select(u => u.DisplayName)
            .FirstOrDefaultAsync();

        _logger.LogInformation("Invite created for {Email} to org {OrgId} by user {InvitedBy}",
            email, orgId, invitedBy);

        await _activityLogService.LogAsync(invitedBy, "INVITE_CREATED", "ORGANIZATION", orgId.ToString(),
            new { Email = email, OrgRole = orgRole });

        return new InviteDto
        {
            InviteId = invite.InviteId,
            Email = invite.Email,
            OrgRole = invite.OrgRole,
            InvitedByName = inviterName,
            ExpiresAt = invite.ExpiresAt,
            CreatedAt = invite.CreatedAt
        };
    }

    public async Task<List<InviteDto>> GetPendingInvitesAsync(int orgId)
    {
        var orgExists = await _context.Organizations.AnyAsync(o => o.OrganizationId == orgId);
        if (!orgExists) throw new KeyNotFoundException($"Organization {orgId} not found.");

        return await _context.OrganizationInvites
            .AsNoTracking()
            .Include(i => i.InvitedByUser)
            .Where(i => i.OrganizationId == orgId
                      && i.AcceptedAt == null
                      && i.ExpiresAt > DateTime.UtcNow)
            .OrderByDescending(i => i.CreatedAt)
            .Select(i => new InviteDto
            {
                InviteId = i.InviteId,
                Email = i.Email,
                OrgRole = i.OrgRole,
                InvitedByName = i.InvitedByUser != null ? i.InvitedByUser.DisplayName : null,
                ExpiresAt = i.ExpiresAt,
                CreatedAt = i.CreatedAt
            })
            .ToListAsync();
    }

    public async Task RevokeInviteAsync(int orgId, int inviteId)
    {
        var invite = await _context.OrganizationInvites
            .FirstOrDefaultAsync(i => i.InviteId == inviteId && i.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Invite {inviteId} not found in organization {orgId}.");

        if (invite.AcceptedAt.HasValue)
        {
            throw new InvalidOperationException("Cannot revoke an already accepted invite.");
        }

        _context.OrganizationInvites.Remove(invite);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Invite {InviteId} revoked from org {OrgId}", inviteId, orgId);
    }

    public async Task<List<OrganizationDto>> ListOrganizationsAsync()
    {
        return await _context.Organizations
            .AsNoTracking()
            .OrderBy(o => o.Name)
            .Select(o => new OrganizationDto
            {
                Id = o.OrganizationId,
                Name = o.Name,
                Slug = o.Slug,
                IsActive = o.IsActive == "Y",
                MaxUsers = o.MaxUsers,
                SubscriptionTier = o.SubscriptionTier,
                CreatedAt = o.CreatedAt
            })
            .ToListAsync();
    }

    public async Task<OrganizationDto> CreateOrganizationAsync(string name, string slug)
    {
        // Check slug uniqueness
        var slugExists = await _context.Organizations
            .AnyAsync(o => o.Slug.ToLower() == slug.ToLower());

        if (slugExists)
        {
            throw new InvalidOperationException("Organization slug already exists.");
        }

        var org = new Organization
        {
            Name = name,
            Slug = slug,
            IsActive = "Y",
            MaxUsers = 10,
            SubscriptionTier = "trial",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        _context.Organizations.Add(org);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Organization {OrgId} created with slug {Slug}", org.OrganizationId, slug);

        return MapToDto(org);
    }

    public async Task<OrganizationMemberDto> CreateOwnerAsync(int orgId, string email, string password, string displayName)
    {
        var org = await _context.Organizations.FindAsync(orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found.");

        // Check if org already has an owner
        var hasOwner = await _context.AppUsers
            .AnyAsync(u => u.OrganizationId == orgId && u.OrgRole == "owner");

        if (hasOwner)
        {
            throw new InvalidOperationException("Organization already has an owner.");
        }

        // Check email uniqueness
        var emailExists = await _context.AppUsers
            .AnyAsync(u => u.Email != null && u.Email.ToLower() == email.ToLower());

        if (emailExists)
        {
            throw new InvalidOperationException("Email already registered.");
        }

        // Generate username from email (prefix before @)
        var username = email.Split('@')[0].ToLowerInvariant();

        // Ensure username uniqueness
        var baseUsername = username;
        var counter = 1;
        while (await _context.AppUsers.AnyAsync(u => u.Username.ToLower() == username.ToLower()))
        {
            username = $"{baseUsername}{counter}";
            counter++;
        }

        var user = new AppUser
        {
            OrganizationId = orgId,
            Username = username,
            DisplayName = displayName,
            Email = email,
            PasswordHash = _authService.HashPassword(password),
            Role = "USER",
            OrgRole = "owner",
            IsActive = "Y",
            IsOrgAdmin = "N",
            MfaEnabled = "N",
            ForcePasswordChange = "Y",
            FailedLoginAttempts = 0,
            CreatedAt = DateTime.UtcNow
        };

        _context.AppUsers.Add(user);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Owner user {UserId} created for organization {OrgId}", user.UserId, orgId);

        return new OrganizationMemberDto
        {
            UserId = user.UserId,
            Email = user.Email,
            DisplayName = user.DisplayName,
            OrgRole = user.OrgRole,
            IsActive = true,
            CreatedAt = user.CreatedAt
        };
    }

    private static OrganizationDto MapToDto(Organization org)
    {
        return new OrganizationDto
        {
            Id = org.OrganizationId,
            Name = org.Name,
            Slug = org.Slug,
            IsActive = org.IsActive == "Y",
            MaxUsers = org.MaxUsers,
            SubscriptionTier = org.SubscriptionTier,
            CreatedAt = org.CreatedAt
        };
    }

    private static string GenerateInviteCode()
    {
        var bytes = RandomNumberGenerator.GetBytes(32);
        return Convert.ToHexStringLower(bytes);
    }
}
