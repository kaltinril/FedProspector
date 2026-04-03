using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("prospect_status_history")]
public class ProspectStatusHistory
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int HistoryId { get; set; }

    [Required]
    public int ProspectId { get; set; }

    [MaxLength(30)]
    public string? OldStatus { get; set; }

    [Required]
    [MaxLength(30)]
    public string NewStatus { get; set; } = string.Empty;

    public int? ChangedBy { get; set; }

    public DateTime ChangedAt { get; set; }

    public int? TimeInOldStatusHours { get; set; }

    // Navigation
    [ForeignKey("ProspectId")]
    public Prospect? Prospect { get; set; }

    [ForeignKey("ChangedBy")]
    public AppUser? ChangedByUser { get; set; }
}
