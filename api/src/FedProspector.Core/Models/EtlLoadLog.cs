using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("etl_load_log")]
public class EtlLoadLog
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int LoadId { get; set; }

    [MaxLength(50)]
    public string SourceSystem { get; set; } = string.Empty;

    [MaxLength(20)]
    public string LoadType { get; set; } = string.Empty;

    [MaxLength(20)]
    public string Status { get; set; } = string.Empty;

    public DateTime StartedAt { get; set; }

    public DateTime? CompletedAt { get; set; }

    public int RecordsRead { get; set; }

    public int RecordsInserted { get; set; }

    public int RecordsUpdated { get; set; }

    public int RecordsUnchanged { get; set; }

    public int RecordsErrored { get; set; }

    public string? ErrorMessage { get; set; }

    [Column(TypeName = "json")]
    public string? Parameters { get; set; }

    [MaxLength(500)]
    public string? SourceFile { get; set; }
}
