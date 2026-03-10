using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("prospect_team_member")]
public class ProspectTeamMember
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [Required]
    public int ProspectId { get; set; }

    [MaxLength(12)]
    public string? UeiSam { get; set; }

    public int? AppUserId { get; set; }

    [MaxLength(50)]
    public string? Role { get; set; }

    public string? Notes { get; set; }

    [Column(TypeName = "decimal(10,2)")]
    public decimal? ProposedHourlyRate { get; set; }

    [Column(TypeName = "decimal(5,2)")]
    public decimal? CommitmentPct { get; set; }

    // Navigation properties
    [ForeignKey("ProspectId")]
    public Prospect? Prospect { get; set; }

    [ForeignKey("AppUserId")]
    public AppUser? AppUser { get; set; }
}
