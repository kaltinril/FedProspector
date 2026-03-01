using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("etl_load_error")]
public class EtlLoadError
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public long Id { get; set; }

    public int LoadId { get; set; }

    [MaxLength(100)]
    public string? RecordIdentifier { get; set; }

    [MaxLength(50)]
    public string? ErrorType { get; set; }

    public string? ErrorMessage { get; set; }

    public string? RawData { get; set; }

    public DateTime? CreatedAt { get; set; }
}
