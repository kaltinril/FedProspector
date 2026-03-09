using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("etl_health_snapshot")]
public class EtlHealthSnapshot
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int SnapshotId { get; set; }

    public DateTime CheckedAt { get; set; }

    [MaxLength(20)]
    public string OverallStatus { get; set; } = string.Empty;

    public int AlertCount { get; set; }

    public int ErrorCount { get; set; }

    public int StaleSourceCount { get; set; }

    [Column(TypeName = "json")]
    public string? Details { get; set; }
}
