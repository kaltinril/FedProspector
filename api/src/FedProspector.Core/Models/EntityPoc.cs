using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("entity_poc")]
public class EntityPoc
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(40)]
    public string PocType { get; set; } = string.Empty;

    [MaxLength(65)]
    public string? FirstName { get; set; }

    [MaxLength(3)]
    public string? MiddleInitial { get; set; }

    [MaxLength(65)]
    public string? LastName { get; set; }

    [MaxLength(50)]
    public string? Title { get; set; }

    [Column("address_line_1")]
    [MaxLength(150)]
    public string? AddressLine1 { get; set; }

    [Column("address_line_2")]
    [MaxLength(150)]
    public string? AddressLine2 { get; set; }

    [MaxLength(40)]
    public string? City { get; set; }

    [MaxLength(55)]
    public string? StateOrProvince { get; set; }

    [MaxLength(50)]
    public string? ZipCode { get; set; }

    [MaxLength(10)]
    public string? ZipCodePlus4 { get; set; }

    [MaxLength(3)]
    public string? CountryCode { get; set; }
}
