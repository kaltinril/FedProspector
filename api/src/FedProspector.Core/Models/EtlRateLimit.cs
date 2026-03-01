using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("etl_rate_limit")]
public class EtlRateLimit
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(50)]
    public string SourceSystem { get; set; } = string.Empty;

    public DateOnly RequestDate { get; set; }

    public int RequestsMade { get; set; }

    public int MaxRequests { get; set; }

    public DateTime? LastRequestAt { get; set; }
}
