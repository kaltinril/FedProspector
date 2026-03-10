using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("opportunity_poc")]
public class OpportunityPoc
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int PocId { get; set; }

    [Required]
    [MaxLength(100)]
    public string NoticeId { get; set; } = string.Empty;

    [Required]
    public int OfficerId { get; set; }

    [Required]
    [MaxLength(20)]
    public string PocType { get; set; } = "PRIMARY";

    public DateTime? CreatedAt { get; set; }

    // Navigation property
    [ForeignKey("NoticeId")]
    public Opportunity? Opportunity { get; set; }
}
