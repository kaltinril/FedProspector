using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("etl_data_quality_rule")]
public class EtlDataQualityRule
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int RuleId { get; set; }

    [MaxLength(100)]
    public string RuleName { get; set; } = string.Empty;

    public string? Description { get; set; }

    [MaxLength(100)]
    public string? TargetTable { get; set; }

    [MaxLength(100)]
    public string? TargetColumn { get; set; }

    [MaxLength(20)]
    public string? RuleType { get; set; }

    [Column(TypeName = "json")]
    public string? RuleDefinition { get; set; }

    [MaxLength(1)]
    public string? IsActive { get; set; } = "Y";

    public int? Priority { get; set; } = 100;
}
