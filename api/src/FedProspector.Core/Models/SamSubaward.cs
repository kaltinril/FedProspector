using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("sam_subaward")]
public class SamSubaward
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(50)]
    public string? PrimePiid { get; set; }

    [MaxLength(10)]
    public string? PrimeAgencyId { get; set; }

    [MaxLength(200)]
    public string? PrimeAgencyName { get; set; }

    [MaxLength(12)]
    public string? PrimeUei { get; set; }

    [MaxLength(500)]
    public string? PrimeName { get; set; }

    [MaxLength(12)]
    public string? SubUei { get; set; }

    [MaxLength(500)]
    public string? SubName { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? SubAmount { get; set; }

    public DateOnly? SubDate { get; set; }

    public string? SubDescription { get; set; }

    [MaxLength(6)]
    public string? NaicsCode { get; set; }

    [MaxLength(10)]
    public string? PscCode { get; set; }

    [MaxLength(50)]
    public string? SubBusinessType { get; set; }

    [MaxLength(6)]
    public string? PopState { get; set; }

    [MaxLength(3)]
    public string? PopCountry { get; set; }

    [MaxLength(10)]
    public string? PopZip { get; set; }

    [MaxLength(3)]
    public string? RecoveryModelQ1 { get; set; }

    [MaxLength(3)]
    public string? RecoveryModelQ2 { get; set; }

    [MaxLength(64)]
    public string? RecordHash { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public DateTime? LastUpdatedAt { get; set; }

    public int? LastLoadId { get; set; }
}
