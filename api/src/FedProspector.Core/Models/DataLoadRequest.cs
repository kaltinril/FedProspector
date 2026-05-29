using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("data_load_request")]
public class DataLoadRequest
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int RequestId { get; set; }

    [MaxLength(30)]
    public string RequestType { get; set; } = string.Empty;

    [MaxLength(200)]
    public string LookupKey { get; set; } = string.Empty;

    [MaxLength(20)]
    public string LookupKeyType { get; set; } = "PIID";

    [MaxLength(20)]
    public string Status { get; set; } = "PENDING";

    public int? RequestedBy { get; set; }

    public DateTime RequestedAt { get; set; } = DateTime.UtcNow;

    public DateTime? StartedAt { get; set; }

    public DateTime? CompletedAt { get; set; }

    public int? LoadId { get; set; }

    public string? ErrorMessage { get; set; }

    [Column(TypeName = "json")]
    public string? ResultSummary { get; set; }

    /// <summary>
    /// UTC timestamp set when the vendor API returned 429 (rate-limited).
    /// The request poller defers reprocessing until this time. NULL otherwise.
    /// Paired with status='PENDING_RETRY'. See Phase 123.
    /// </summary>
    public DateTime? RetryAfter { get; set; }
}
