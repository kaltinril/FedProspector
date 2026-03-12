using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("entity_address")]
public class EntityAddress
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    [MaxLength(12)]
    public string UeiSam { get; set; } = string.Empty;

    [MaxLength(10)]
    public string AddressType { get; set; } = string.Empty;

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

    [MaxLength(10)]
    public string? CongressionalDistrict { get; set; }

    // Navigation property
    [ForeignKey("UeiSam")]
    public Entity? Entity { get; set; }
}
