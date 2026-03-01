using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("opportunity_relationship")]
public class OpportunityRelationship
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(100)]
    public string ParentNoticeId { get; set; } = string.Empty;

    [MaxLength(100)]
    public string ChildNoticeId { get; set; } = string.Empty;

    [MaxLength(30)]
    public string RelationshipType { get; set; } = string.Empty;

    public int? CreatedBy { get; set; }

    public DateTime? CreatedAt { get; set; }

    public string? Notes { get; set; }
}
