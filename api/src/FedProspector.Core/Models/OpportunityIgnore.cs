using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("opportunity_ignore")]
public class OpportunityIgnore
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int IgnoreId { get; set; }

    [Required]
    public int UserId { get; set; }

    [Required]
    [MaxLength(100)]
    public string NoticeId { get; set; } = string.Empty;

    public DateTime IgnoredAt { get; set; }

    [MaxLength(500)]
    public string? Reason { get; set; }

    // Navigation properties
    [ForeignKey("UserId")]
    public AppUser? User { get; set; }

    [ForeignKey("NoticeId")]
    public Opportunity? Opportunity { get; set; }
}
