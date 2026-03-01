using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("sam_exclusion")]
public class SamExclusion
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(12)]
    public string? Uei { get; set; }

    [MaxLength(10)]
    public string? CageCode { get; set; }

    [MaxLength(500)]
    public string? EntityName { get; set; }

    [MaxLength(100)]
    public string? FirstName { get; set; }

    [MaxLength(100)]
    public string? MiddleName { get; set; }

    [MaxLength(100)]
    public string? LastName { get; set; }

    [MaxLength(20)]
    public string? Suffix { get; set; }

    [MaxLength(20)]
    public string? Prefix { get; set; }

    [MaxLength(50)]
    public string? ExclusionType { get; set; }

    [MaxLength(50)]
    public string? ExclusionProgram { get; set; }

    [MaxLength(10)]
    public string? ExcludingAgencyCode { get; set; }

    [MaxLength(200)]
    public string? ExcludingAgencyName { get; set; }

    public DateOnly? ActivationDate { get; set; }

    public DateOnly? TerminationDate { get; set; }

    public string? AdditionalComments { get; set; }

    [MaxLength(64)]
    public string? RecordHash { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public DateTime? LastUpdatedAt { get; set; }

    public int? LastLoadId { get; set; }
}
