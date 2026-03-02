using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("prospect")]
public class Prospect
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int ProspectId { get; set; }

    [Required]
    public int OrganizationId { get; set; }

    [Required]
    [MaxLength(100)]
    public string NoticeId { get; set; } = string.Empty;

    public int? AssignedTo { get; set; }

    public int? CaptureManagerId { get; set; }

    [Required]
    [MaxLength(30)]
    public string Status { get; set; } = "NEW";

    [MaxLength(20)]
    public string? ProposalStatus { get; set; }

    [MaxLength(10)]
    public string? Priority { get; set; } = "MEDIUM";

    public DateOnly? DecisionDate { get; set; }

    public DateOnly? BidSubmittedDate { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? EstimatedValue { get; set; }

    [Column(TypeName = "decimal(10,2)")]
    public decimal? EstimatedEffortHours { get; set; }

    [Column(TypeName = "decimal(5,2)")]
    public decimal? WinProbability { get; set; }

    [Column(TypeName = "decimal(5,2)")]
    public decimal? GoNoGoScore { get; set; }

    [MaxLength(1)]
    public string? TeamingRequired { get; set; } = "N";

    [Column(TypeName = "decimal(10,2)")]
    public decimal? EstimatedProposalCost { get; set; }

    [Column(TypeName = "decimal(5,2)")]
    public decimal? EstimatedGrossMarginPct { get; set; }

    public int? ProposalDueDays { get; set; }

    [MaxLength(20)]
    public string? Outcome { get; set; }

    public DateOnly? OutcomeDate { get; set; }

    public string? OutcomeNotes { get; set; }

    [MaxLength(50)]
    public string? ContractAwardId { get; set; }

    public DateTime? CreatedAt { get; set; }

    public DateTime? UpdatedAt { get; set; }

    // Navigation property
    [ForeignKey("OrganizationId")]
    public Organization? Organization { get; set; }
}
