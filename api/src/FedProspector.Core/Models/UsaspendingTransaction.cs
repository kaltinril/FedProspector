using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("usaspending_transaction")]
public class UsaspendingTransaction
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public long Id { get; set; }

    [Required]
    [MaxLength(100)]
    public string AwardId { get; set; } = string.Empty;

    [Required]
    public DateOnly ActionDate { get; set; }

    [MaxLength(20)]
    public string? ModificationNumber { get; set; }

    [MaxLength(5)]
    public string? ActionType { get; set; }

    [MaxLength(100)]
    public string? ActionTypeDescription { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? FederalActionObligation { get; set; }

    public string? Description { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public int? LastLoadId { get; set; }
}
