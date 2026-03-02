using FedProspector.Core.Models;
using FedProspector.Core.Models.Views;
using Microsoft.EntityFrameworkCore;

namespace FedProspector.Infrastructure.Data;

/// <summary>
/// Central data access context for the Federal Contract Prospecting database.
/// Maps 47 entity models to the fed_contracts MySQL database.
///
/// Schema Ownership:
///   - Reference tables (ref_*), entity/ETL/federal data tables are owned by the
///     Python DDL and ETL pipeline. EF Core maps them as read-only (no migrations).
///   - Application tables (app_user, prospect, proposal, etc.) are owned by EF Core
///     and may have migrations generated for them in the future.
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
    public DbSet<UsaspendingTransaction> UsaspendingTransactions { get; set; }

    // -----------------------------------------------------------------------
    // ETL Tables (4)
    // -----------------------------------------------------------------------

    public DbSet<EtlLoadLog> EtlLoadLogs { get; set; }
    public DbSet<EtlLoadError> EtlLoadErrors { get; set; }
    public DbSet<EtlDataQualityRule> EtlDataQualityRules { get; set; }
    public DbSet<EtlRateLimit> EtlRateLimits { get; set; }

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
    // Web API / App Tables (5)
    // -----------------------------------------------------------------------

    public DbSet<AppUser> AppUsers { get; set; }
    public DbSet<AppSession> AppSessions { get; set; }
    public DbSet<SavedSearch> SavedSearches { get; set; }
    public DbSet<ActivityLog> ActivityLogs { get; set; }
    public DbSet<Notification> Notifications { get; set; }

    // -----------------------------------------------------------------------
    // Database Views (4 - keyless, read-only)
    // -----------------------------------------------------------------------

    public DbSet<TargetOpportunityView> TargetOpportunities { get; set; }
    public DbSet<CompetitorAnalysisView> CompetitorAnalyses { get; set; }
    public DbSet<ProcurementIntelligenceView> ProcurementIntelligence { get; set; }
    public DbSet<IncumbentProfileView> IncumbentProfiles { get; set; }

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

        modelBuilder.Entity<FpdsContract>()
            .HasKey(e => new { e.ContractId, e.ModificationNumber });

        // ----- Unique Constraints -----

        modelBuilder.Entity<UsaspendingTransaction>()
            .HasIndex(e => new { e.AwardId, e.ModificationNumber, e.ActionDate })
            .IsUnique();

        modelBuilder.Entity<Prospect>()
            .HasIndex(e => e.NoticeId)
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

        // ----- JSON Column Mappings -----
        // Pomelo handles [Column(TypeName = "json")] via data annotations on the
        // model properties. Explicit Fluent API calls here for clarity and to
        // ensure correct mapping regardless of provider behavior.

        modelBuilder.Entity<EtlLoadLog>()
            .Property(e => e.Parameters)
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

        modelBuilder.Entity<Opportunity>()
            .Property(e => e.ResourceLinks)
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
    }
}
