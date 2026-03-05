using System.ComponentModel.DataAnnotations;

namespace FedProspector.Core.DTOs.Organizations;

public class UpdateOrgProfileRequest
{
    [MaxLength(200)]
    public string? Name { get; set; }

    [MaxLength(300)]
    public string? LegalName { get; set; }

    [MaxLength(300)]
    public string? DbaName { get; set; }

    [MaxLength(13)]
    public string? UeiSam { get; set; }

    [MaxLength(5)]
    public string? CageCode { get; set; }

    [MaxLength(10)]
    public string? Ein { get; set; }

    [MaxLength(200)]
    public string? AddressLine1 { get; set; }

    [MaxLength(200)]
    public string? AddressLine2 { get; set; }

    [MaxLength(100)]
    public string? City { get; set; }

    [MaxLength(2)]
    public string? StateCode { get; set; }

    [MaxLength(10)]
    public string? ZipCode { get; set; }

    [MaxLength(3)]
    public string? CountryCode { get; set; }

    [MaxLength(20)]
    public string? Phone { get; set; }

    [MaxLength(500)]
    public string? Website { get; set; }

    public int? EmployeeCount { get; set; }

    public decimal? AnnualRevenue { get; set; }

    [Range(1, 12)]
    public byte? FiscalYearEndMonth { get; set; }

    [MaxLength(50)]
    public string? EntityStructure { get; set; }

    public bool? ProfileCompleted { get; set; }
}
