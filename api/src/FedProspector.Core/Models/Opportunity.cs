using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("opportunity")]
public class Opportunity
{
    [Key]
    [MaxLength(100)]
    public string NoticeId { get; set; } = string.Empty;

    [MaxLength(500)]
    public string? Title { get; set; }

    [MaxLength(100)]
    public string? SolicitationNumber { get; set; }

    [MaxLength(200)]
    public string? DepartmentName { get; set; }

    [MaxLength(200)]
    public string? SubTier { get; set; }

    [MaxLength(200)]
    public string? Office { get; set; }

    public DateOnly? PostedDate { get; set; }

    public DateTime? ResponseDeadline { get; set; }

    public DateOnly? ArchiveDate { get; set; }

    [MaxLength(50)]
    public string? Type { get; set; }

    [MaxLength(50)]
    public string? BaseType { get; set; }

    [MaxLength(20)]
    public string? SetAsideCode { get; set; }

    [MaxLength(200)]
    public string? SetAsideDescription { get; set; }

    [MaxLength(10)]
    public string? ClassificationCode { get; set; }

    [MaxLength(6)]
    public string? NaicsCode { get; set; }

    [MaxLength(6)]
    public string? PopState { get; set; }

    [MaxLength(10)]
    public string? PopZip { get; set; }

    [MaxLength(3)]
    public string? PopCountry { get; set; }

    [MaxLength(100)]
    public string? PopCity { get; set; }

    public DateOnly? PeriodOfPerformanceStart { get; set; }

    public DateOnly? PeriodOfPerformanceEnd { get; set; }

    [MaxLength(1)]
    public string? SecurityClearanceRequired { get; set; }

    [MaxLength(13)]
    public string? IncumbentUei { get; set; }

    [MaxLength(200)]
    public string? IncumbentName { get; set; }

    [MaxLength(50)]
    public string? ContractVehicleType { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? EstimatedContractValue { get; set; }

    [MaxLength(1)]
    public string? Active { get; set; }

    [MaxLength(200)]
    public string? AwardNumber { get; set; }

    public DateOnly? AwardDate { get; set; }

    [Column(TypeName = "decimal(15,2)")]
    public decimal? AwardAmount { get; set; }

    [MaxLength(12)]
    public string? AwardeeUei { get; set; }

    [MaxLength(200)]
    public string? AwardeeName { get; set; }

    [MaxLength(10)]
    public string? AwardeeCageCode { get; set; }

    [MaxLength(100)]
    public string? AwardeeCity { get; set; }

    [MaxLength(6)]
    public string? AwardeeState { get; set; }

    [MaxLength(10)]
    public string? AwardeeZip { get; set; }

    [MaxLength(500)]
    public string? FullParentPathName { get; set; }

    [MaxLength(200)]
    public string? FullParentPathCode { get; set; }

    [MaxLength(500)]
    public string? DescriptionUrl { get; set; }

    public string? DescriptionText { get; set; }

    [MaxLength(500)]
    public string? Link { get; set; }

    [Column(TypeName = "json")]
    public string? ResourceLinks { get; set; }

    [MaxLength(20)]
    public string? ContractingOfficeId { get; set; }

    [MaxLength(64)]
    public string? RecordHash { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public DateTime? LastLoadedAt { get; set; }

    public int? LastLoadId { get; set; }
}
