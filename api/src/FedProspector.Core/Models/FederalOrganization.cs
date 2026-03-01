using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("federal_organization")]
public class FederalOrganization
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.None)]
    public int FhOrgId { get; set; }

    [MaxLength(500)]
    public string? FhOrgName { get; set; }

    [MaxLength(50)]
    public string? FhOrgType { get; set; }

    public string? Description { get; set; }

    [MaxLength(20)]
    public string? Status { get; set; }

    [MaxLength(20)]
    public string? AgencyCode { get; set; }

    [MaxLength(20)]
    public string? OldfpdsOfficeCode { get; set; }

    [MaxLength(10)]
    public string? Cgac { get; set; }

    public int? ParentOrgId { get; set; }

    public int? Level { get; set; }

    public DateOnly? CreatedDate { get; set; }

    public DateOnly? LastModifiedDate { get; set; }

    [MaxLength(64)]
    public string? RecordHash { get; set; }

    public DateTime? FirstLoadedAt { get; set; }

    public DateTime? LastLoadedAt { get; set; }

    public int? LastLoadId { get; set; }
}
