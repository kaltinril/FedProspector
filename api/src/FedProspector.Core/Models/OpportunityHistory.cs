using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("opportunity_history")]
public class OpportunityHistory
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public long Id { get; set; }

    [MaxLength(100)]
    public string NoticeId { get; set; } = string.Empty;

    [MaxLength(100)]
    public string FieldName { get; set; } = string.Empty;

    public string? OldValue { get; set; }

    public string? NewValue { get; set; }

    public DateTime? ChangedAt { get; set; }

    public int LoadId { get; set; }
}
