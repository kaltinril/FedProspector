using FedProspector.Core.Models;
using FedProspector.Core.Models.Views;
using Microsoft.EntityFrameworkCore;

namespace FedProspector.Infrastructure.Data;

/// <summary>
/// Central data access context for the Federal Contract Prospecting database.
/// Maps 50 entity models to the fed_contracts MySQL database.
///
/// Schema Ownership:
///   - Reference tables (ref_*), entity/ETL/federal data tables are owned by the
///     Python DDL and ETL pipeline. EF Core maps them as read-only (no migrations).
///   - Application tables (app_user, prospect, proposal, etc.) are owned by EF Core
///     and may have migrations generated for them in the future.
///   - Multi-tenancy tables (organization, organization_invite) added in Phase 14.5.
/// </summary>
public class FedProspectorDbContext : DbContext
{
    public FedProspectorDbContext(DbContextOptions<FedProspectorDbContext> options)
        : base(options)
    {
    }

    // -----------------------------------------------------------------------
    // Reference Tables (11)
    // -----------------------------------------------------------------------

    public DbSet<RefNaicsCode> RefNaicsCodes { get; set; }
    public DbSet<RefSbaSizeStandard> RefSbaSizeStandards { get; set; }
    public DbSet<RefNaicsFootnote> RefNaicsFootnotes { get; set; }
    public DbSet<RefPscCode> RefPscCodes { get; set; }
    public DbSet<RefCountryCode> RefCountryCodes { get; set; }
    public DbSet<RefStateCode> RefStateCodes { get; set; }
    public DbSet<RefFipsCounty> RefFipsCounties { get; set; }
    public DbSet<RefBusinessType> RefBusinessTypes { get; set; }
    public DbSet<RefEntityStructure> RefEntityStructures { get; set; }
    public DbSet<RefSetAsideType> RefSetAsideTypes { get; set; }
    public DbSet<RefSbaType> RefSbaTypes { get; set; }

    // -----------------------------------------------------------------------
    // Entity Tables (8)
    // -----------------------------------------------------------------------

    public DbSet<Entity> Entities { get; set; }
    public DbSet<EntityAddress> EntityAddresses { get; set; }
    public DbSet<EntityNaics> EntityNaicsCodes { get; set; }
    public DbSet<EntityPsc> EntityPscCodes { get; set; }
    public DbSet<EntityBusinessType> EntityBusinessTypes { get; set; }
    public DbSet<EntitySbaCertification> EntitySbaCertifications { get; set; }
    public DbSet<EntityPoc> EntityPocs { get; set; }
    public DbSet<EntityDisasterResponse> EntityDisasterResponses { get; set; }

    // -----------------------------------------------------------------------
    // Entity History
    // -----------------------------------------------------------------------

    public DbSet<EntityHistory> EntityHistories { get; set; }

    // -----------------------------------------------------------------------
    // Opportunity Tables (5)
    // -----------------------------------------------------------------------

    public DbSet<Opportunity> Opportunities { get; set; }
    public DbSet<OpportunityHistory> OpportunityHistories { get; set; }
    public DbSet<OpportunityRelationship> OpportunityRelationships { get; set; }
    public DbSet<ContractingOfficer> ContractingOfficers { get; set; }
    public DbSet<OpportunityPoc> OpportunityPocs { get; set; }

    // -----------------------------------------------------------------------
    // Attachment Tables (6 — normalized dedup schema, Phase 110ZZZ)
    // -----------------------------------------------------------------------

    public DbSet<SamAttachment> SamAttachments { get; set; }
    public DbSet<AttachmentDocument> AttachmentDocuments { get; set; }
    public DbSet<OpportunityAttachment> OpportunityAttachments { get; set; }
    public DbSet<DocumentIntelSummary> DocumentIntelSummaries { get; set; }
    public DbSet<DocumentIntelEvidence> DocumentIntelEvidence { get; set; }
    public DbSet<OpportunityAttachmentSummary> OpportunityAttachmentSummaries { get; set; }
    public DbSet<DocumentIdentifierRef> DocumentIdentifierRefs { get; set; }

    // -----------------------------------------------------------------------
    // Federal / Awards Tables (5)
    // -----------------------------------------------------------------------

    public DbSet<FederalOrganization> FederalOrganizations { get; set; }
    public DbSet<FpdsContract> FpdsContracts { get; set; }
    public DbSet<GsaLaborRate> GsaLaborRates { get; set; }
    public DbSet<SamExclusion> SamExclusions { get; set; }
    public DbSet<SamSubaward> SamSubawards { get; set; }

    // -----------------------------------------------------------------------
    // USASpending Tables (2)
    // -----------------------------------------------------------------------

    public DbSet<UsaspendingAward> UsaspendingAwards { get; set; }
    public DbSet<UsaspendingAwardSummary> UsaspendingAwardSummaries { get; set; }
    public DbSet<UsaspendingTransaction> UsaspendingTransactions { get; set; }

    // -----------------------------------------------------------------------
    // ETL Tables (5)
    // -----------------------------------------------------------------------

    public DbSet<EtlLoadLog> EtlLoadLogs { get; set; }
    public DbSet<EtlLoadError> EtlLoadErrors { get; set; }
    public DbSet<EtlDataQualityRule> EtlDataQualityRules { get; set; }
    public DbSet<EtlRateLimit> EtlRateLimits { get; set; }
    public DbSet<EtlHealthSnapshot> EtlHealthSnapshots { get; set; }
    public DbSet<DataLoadRequest> DataLoadRequests { get; set; }

    // -----------------------------------------------------------------------
    // Prospecting / Capture Management Tables (6)
    // -----------------------------------------------------------------------

    public DbSet<Prospect> Prospects { get; set; }
    public DbSet<ProspectNote> ProspectNotes { get; set; }
    public DbSet<ProspectTeamMember> ProspectTeamMembers { get; set; }
    public DbSet<Proposal> Proposals { get; set; }
    public DbSet<ProposalDocument> ProposalDocuments { get; set; }
    public DbSet<ProposalMilestone> ProposalMilestones { get; set; }

    // -----------------------------------------------------------------------
    // Web API / App Tables (7)
    // -----------------------------------------------------------------------

    public DbSet<Organization> Organizations { get; set; }
    public DbSet<OrganizationInvite> OrganizationInvites { get; set; }
    public DbSet<OrganizationNaics> OrganizationNaics { get; set; }
    public DbSet<OrganizationCertification> OrganizationCertifications { get; set; }
    public DbSet<OrganizationPastPerformance> OrganizationPastPerformances { get; set; }
    public DbSet<OrganizationEntity> OrganizationEntities { get; set; }
    public DbSet<AppUser> AppUsers { get; set; }
    public DbSet<AppSession> AppSessions { get; set; }
    public DbSet<SavedSearch> SavedSearches { get; set; }
    public DbSet<ActivityLog> ActivityLogs { get; set; }
    public DbSet<Notification> Notifications { get; set; }

    // -----------------------------------------------------------------------
    // Database Views (9 - keyless, read-only)
    // -----------------------------------------------------------------------

    public DbSet<TargetOpportunityView> TargetOpportunities { get; set; }
    public DbSet<CompetitorAnalysisView> CompetitorAnalyses { get; set; }
    public DbSet<ProcurementIntelligenceView> ProcurementIntelligence { get; set; }
    public DbSet<IncumbentProfileView> IncumbentProfiles { get; set; }
    public DbSet<RefPscCodeLatest> RefPscCodeLatest { get; set; }
    public DbSet<SetAsideShiftView> SetAsideShifts { get; set; }
    public DbSet<SetAsideTrendView> SetAsideTrends { get; set; }
    public DbSet<MonthlySpendView> MonthlySpends { get; set; }
    public DbSet<VendorMarketShareView> VendorMarketShares { get; set; }

    // -----------------------------------------------------------------------
    // Fluent API Configuration
    // -----------------------------------------------------------------------

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // ----- Composite Primary Keys -----
        // EF Core does not support composite keys via [Key] attributes alone;
        // these require Fluent API configuration.

        modelBuilder.Entity<RefNaicsFootnote>()
            .HasKey(e => new { e.FootnoteId, e.Section });

        modelBuilder.Entity<RefPscCode>()
            .HasKey(e => new { e.PscCode, e.StartDate });

        modelBuilder.Entity<RefStateCode>()
            .HasKey(e => new { e.StateCode, e.CountryCode });

        modelBuilder.Entity<UsaspendingAwardSummary>()
            .HasKey(s => new { s.NaicsCode, s.AgencyName });

        modelBuilder.Entity<FpdsContract>()
            .HasKey(e => new { e.ContractId, e.ModificationNumber });

        modelBuilder.Entity<OpportunityAttachment>()
            .HasKey(m => new { m.NoticeId, m.AttachmentId });

        modelBuilder.Entity<OpportunityAttachment>()
            .HasOne(m => m.SamAttachment)
            .WithMany()
            .HasForeignKey(m => m.AttachmentId)
            .HasPrincipalKey(s => s.AttachmentId);

        modelBuilder.Entity<AttachmentDocument>()
            .HasOne(d => d.SamAttachment)
            .WithMany()
            .HasForeignKey(d => d.AttachmentId)
            .HasPrincipalKey(s => s.AttachmentId);

        // ----- Unique Constraints -----

        modelBuilder.Entity<UsaspendingTransaction>()
            .HasIndex(e => new { e.AwardId, e.ModificationNumber, e.ActionDate })
            .IsUnique();

        modelBuilder.Entity<Prospect>()
            .HasIndex(e => new { e.OrganizationId, e.NoticeId })
            .IsUnique();

        modelBuilder.Entity<OpportunityPoc>()
            .HasIndex(e => new { e.NoticeId, e.OfficerId, e.PocType })
            .IsUnique();

        modelBuilder.Entity<Proposal>()
            .HasIndex(e => e.ProspectId)
            .IsUnique();

        modelBuilder.Entity<AppSession>()
            .HasIndex(e => e.TokenHash)
            .IsUnique();

        modelBuilder.Entity<AppSession>()
            .HasIndex(e => e.RefreshTokenHash)
            .HasDatabaseName("IX_app_session_refresh_token_hash");

        modelBuilder.Entity<Organization>()
            .HasIndex(e => e.Slug)
            .IsUnique();

        modelBuilder.Entity<OrganizationInvite>()
            .HasIndex(e => e.InviteCode)
            .IsUnique();

        // ----- JSON Column Mappings -----
        // Pomelo handles [Column(TypeName = "json")] via data annotations on the
        // model properties. Explicit Fluent API calls here for clarity and to
        // ensure correct mapping regardless of provider behavior.

        modelBuilder.Entity<EtlLoadLog>()
            .Property(e => e.Parameters)
            .HasColumnType("json");

        modelBuilder.Entity<EtlHealthSnapshot>()
            .Property(e => e.Details)
            .HasColumnType("json");

        modelBuilder.Entity<EtlDataQualityRule>()
            .Property(e => e.RuleDefinition)
            .HasColumnType("json");

        modelBuilder.Entity<SavedSearch>()
            .Property(e => e.FilterCriteria)
            .HasColumnType("json");

        modelBuilder.Entity<ActivityLog>()
            .Property(e => e.Details)
            .HasColumnType("json");

        modelBuilder.Entity<DataLoadRequest>()
            .Property(e => e.ResultSummary)
            .HasColumnType("json");

        modelBuilder.Entity<Opportunity>()
            .Property(e => e.ResourceLinks)
            .HasColumnType("json");

        modelBuilder.Entity<DocumentIntelSummary>()
            .Property(e => e.LaborCategories)
            .HasColumnType("json");

        modelBuilder.Entity<DocumentIntelSummary>()
            .Property(e => e.KeyRequirements)
            .HasColumnType("json");

        modelBuilder.Entity<DocumentIntelSummary>()
            .Property(e => e.ConfidenceDetails)
            .HasColumnType("json");

        modelBuilder.Entity<DocumentIntelSummary>()
            .Property(e => e.CitationOffsets)
            .HasColumnType("json");

        modelBuilder.Entity<OpportunityAttachmentSummary>()
            .Property(e => e.LaborCategories)
            .HasColumnType("json");

        modelBuilder.Entity<OpportunityAttachmentSummary>()
            .Property(e => e.KeyRequirements)
            .HasColumnType("json");

        modelBuilder.Entity<OpportunityAttachmentSummary>()
            .Property(e => e.ConfidenceDetails)
            .HasColumnType("json");

        modelBuilder.Entity<OpportunityAttachmentSummary>()
            .Property(e => e.CitationOffsets)
            .HasColumnType("json");

        // ----- Y/N Boolean Value Converters -----
        // All CHAR(1) Y/N columns currently use string properties.
        // If we switch to bool properties in the future, add ValueConverters here:
        //
        //   var ynToBoolConverter = new ValueConverter<bool, string>(
        //       v => v ? "Y" : "N",
        //       v => v == "Y"
        //   );
        //
        // Then apply to each property:
        //   modelBuilder.Entity<Entity>()
        //       .Property(e => e.IsActive)
        //       .HasConversion(ynToBoolConverter);

        // ----- Multi-Tenancy Relationships (Phase 14.5) -----

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.Users)
            .WithOne(u => u.Organization)
            .HasForeignKey(u => u.OrganizationId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.Invites)
            .WithOne(i => i.Organization)
            .HasForeignKey(i => i.OrganizationId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.Prospects)
            .WithOne(p => p.Organization)
            .HasForeignKey(p => p.OrganizationId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.SavedSearches)
            .WithOne(s => s.Organization)
            .HasForeignKey(s => s.OrganizationId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.ActivityLogs)
            .WithOne(a => a.Organization)
            .HasForeignKey(a => a.OrganizationId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.NaicsCodes)
            .WithOne(n => n.Organization)
            .HasForeignKey(n => n.OrganizationId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.Certifications)
            .WithOne(c => c.Organization)
            .HasForeignKey(c => c.OrganizationId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.PastPerformances)
            .WithOne(p => p.Organization)
            .HasForeignKey(p => p.OrganizationId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<Organization>()
            .HasMany(o => o.LinkedEntities)
            .WithOne(oe => oe.Organization)
            .HasForeignKey(oe => oe.OrganizationId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<OrganizationEntity>()
            .HasIndex(e => new { e.OrganizationId, e.UeiSam, e.Relationship })
            .IsUnique();

        modelBuilder.Entity<OrganizationEntity>()
            .HasOne(oe => oe.Entity)
            .WithMany()
            .HasForeignKey(oe => oe.UeiSam)
            .HasPrincipalKey(e => e.UeiSam)
            .IsRequired();

        modelBuilder.Entity<AppUser>()
            .HasOne(u => u.InvitedByUser)
            .WithMany()
            .HasForeignKey(u => u.InvitedBy)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<AppSession>()
            .HasOne(s => s.User)
            .WithMany()
            .HasForeignKey(s => s.UserId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<OrganizationInvite>()
            .HasOne(i => i.InvitedByUser)
            .WithMany()
            .HasForeignKey(i => i.InvitedBy)
            .OnDelete(DeleteBehavior.Restrict);

        // ----- Soft-Delete Query Filters -----
        modelBuilder.Entity<UsaspendingAward>()
            .HasQueryFilter(a => a.DeletedAt == null);

        // ----- Cross-Schema Navigations (no DB-level FK) -----
        // Allow EF Core JOINs without real foreign keys.
        // Not all awards have matching SAM entities, so IsRequired(false).
        // WithMany() with no argument avoids an inverse collection on Entity.

        modelBuilder.Entity<UsaspendingAward>()
            .HasOne(ua => ua.RecipientEntity)
            .WithMany()
            .HasForeignKey(ua => ua.RecipientUei)
            .HasPrincipalKey(e => e.UeiSam)
            .IsRequired(false);

        modelBuilder.Entity<FpdsContract>()
            .HasOne(fc => fc.VendorEntity)
            .WithMany()
            .HasForeignKey(fc => fc.VendorUei)
            .HasPrincipalKey(e => e.UeiSam)
            .IsRequired(false);

        // ----- Database Views (keyless entity types) -----
        modelBuilder.Entity<TargetOpportunityView>()
            .HasNoKey()
            .ToView("v_target_opportunities");

        modelBuilder.Entity<CompetitorAnalysisView>()
            .HasNoKey()
            .ToView("v_competitor_analysis");

        modelBuilder.Entity<ProcurementIntelligenceView>()
            .HasNoKey()
            .ToView("v_procurement_intelligence");

        modelBuilder.Entity<IncumbentProfileView>()
            .HasNoKey()
            .ToView("v_incumbent_profile");

        modelBuilder.Entity<RefPscCodeLatest>()
            .HasNoKey()
            .ToView("ref_psc_code_latest");

        modelBuilder.Entity<SetAsideShiftView>()
            .HasNoKey()
            .ToView("v_set_aside_shift");

        modelBuilder.Entity<SetAsideTrendView>()
            .HasNoKey()
            .ToView("v_set_aside_trend");

        modelBuilder.Entity<MonthlySpendView>()
            .HasNoKey()
            .ToView("v_monthly_spend");

        modelBuilder.Entity<VendorMarketShareView>()
            .HasNoKey()
            .ToView("v_vendor_market_share");
    }
}
