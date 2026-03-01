using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("ref_naics_code")]
public class RefNaicsCode
{
    [Key]
    [MaxLength(11)]
    public string NaicsCode { get; set; } = string.Empty;

    [MaxLength(500)]
    public string Description { get; set; } = string.Empty;

    public byte? CodeLevel { get; set; }

    [MaxLength(30)]
    public string? LevelName { get; set; }

    [MaxLength(11)]
    public string? ParentCode { get; set; }

    [MaxLength(4)]
    public string? YearVersion { get; set; }

    [MaxLength(1)]
    public string? IsActive { get; set; } = "Y";

    [MaxLength(5)]
    public string? FootnoteId { get; set; }

    public DateTime? CreatedAt { get; set; }

    public DateTime? UpdatedAt { get; set; }
}
