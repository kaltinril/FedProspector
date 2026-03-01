using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("proposal")]
public class Proposal
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int ProposalId { get; set; }

    [Required]
    public int ProspectId { get; set; }

    [MaxLength(50)]
    public string? ProposalNumber { get; set; }

    public DateTime? SubmissionDeadline { get; set; }

    public DateTime? SubmittedAt { get; set; }

    [Required]
    [MaxLength(20)]
    public string ProposalStatus { get; set; } = "DRAFT";

    [Column(TypeName = "decimal(15,2)")]
    public decimal? EstimatedValue { get; set; }

    [Column(TypeName = "decimal(5,2)")]
    public decimal? WinProbabilityPct { get; set; }

    public string? LessonsLearned { get; set; }

    public DateTime? CreatedAt { get; set; }

    public DateTime? UpdatedAt { get; set; }
}
