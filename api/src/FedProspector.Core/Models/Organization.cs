using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("organization")]
public class Organization
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(200)]
    public string Name { get; set; } = string.Empty;

    [Required]
    [MaxLength(100)]
    public string Slug { get; set; } = string.Empty;

    [Required]
    [MaxLength(1)]
    public string IsActive { get; set; } = "Y";

    [Required]
    public int MaxUsers { get; set; } = 10;

    [MaxLength(50)]
    public string? SubscriptionTier { get; set; } = "trial";

    // --- Company Profile Fields (Phase 20.8) ---

    [MaxLength(300)]
    public string? LegalName { get; set; }

    [MaxLength(300)]
    public string? DbaName { get; set; }

    [MaxLength(13)]
    public string? UeiSam { get; set; }

    [MaxLength(5)]
    public string? CageCode { get; set; }

    [MaxLength(10)]
    public string? Ein { get; set; }

    [MaxLength(200)]
    public string? AddressLine1 { get; set; }

    [MaxLength(200)]
    public string? AddressLine2 { get; set; }

    [MaxLength(100)]
    public string? City { get; set; }

    [MaxLength(2)]
    public string? StateCode { get; set; }

    [MaxLength(10)]
    public string? ZipCode { get; set; }

    [MaxLength(3)]
    public string? CountryCode { get; set; } = "USA";

    [MaxLength(20)]
    public string? Phone { get; set; }

    [MaxLength(500)]
    public string? Website { get; set; }

    public int? EmployeeCount { get; set; }

    [Column(TypeName = "decimal(18,2)")]
    public decimal? AnnualRevenue { get; set; }

    public byte? FiscalYearEndMonth { get; set; } = 12;

    [MaxLength(50)]
    public string? EntityStructure { get; set; }

    [Required]
    [MaxLength(1)]
    public string ProfileCompleted { get; set; } = "N";

    public DateTime? ProfileCompletedAt { get; set; }

    // --- End Company Profile Fields ---

    [Required]
    public DateTime CreatedAt { get; set; }

    [Required]
    public DateTime UpdatedAt { get; set; }

    // Navigation properties
    public ICollection<AppUser> Users { get; set; } = new List<AppUser>();
    public ICollection<OrganizationInvite> Invites { get; set; } = new List<OrganizationInvite>();
    public ICollection<Prospect> Prospects { get; set; } = new List<Prospect>();
    public ICollection<SavedSearch> SavedSearches { get; set; } = new List<SavedSearch>();
    public ICollection<ActivityLog> ActivityLogs { get; set; } = new List<ActivityLog>();
    public ICollection<OrganizationNaics> NaicsCodes { get; set; } = new List<OrganizationNaics>();
    public ICollection<OrganizationCertification> Certifications { get; set; } = new List<OrganizationCertification>();
    public ICollection<OrganizationPastPerformance> PastPerformances { get; set; } = new List<OrganizationPastPerformance>();
    public ICollection<OrganizationEntity> LinkedEntities { get; set; } = new List<OrganizationEntity>();
}
