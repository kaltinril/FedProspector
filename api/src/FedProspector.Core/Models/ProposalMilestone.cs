using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("proposal_milestone")]
public class ProposalMilestone
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int MilestoneId { get; set; }

    [Required]
    public int ProposalId { get; set; }

    [Required]
    [MaxLength(100)]
    public string MilestoneName { get; set; } = string.Empty;

    public DateOnly? DueDate { get; set; }

    public DateOnly? CompletedDate { get; set; }

    public int? AssignedTo { get; set; }

    [Required]
    [MaxLength(20)]
    public string Status { get; set; } = "PENDING";

    public string? Notes { get; set; }

    public DateTime? CreatedAt { get; set; }

    // Navigation properties
    [ForeignKey("ProposalId")]
    public Proposal? Proposal { get; set; }

    [ForeignKey("AssignedTo")]
    public AppUser? AssignedToUser { get; set; }
}
