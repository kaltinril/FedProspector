namespace FedProspector.Core.DTOs.Organizations;

public class OrgProfileDto
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string? LegalName { get; set; }
    public string? DbaName { get; set; }
    public string? UeiSam { get; set; }
    public string? CageCode { get; set; }
    public string? Ein { get; set; }
    public string? AddressLine1 { get; set; }
    public string? AddressLine2 { get; set; }
    public string? City { get; set; }
    public string? StateCode { get; set; }
    public string? ZipCode { get; set; }
    public string? CountryCode { get; set; }
    public string? Phone { get; set; }
    public string? Website { get; set; }
    public int? EmployeeCount { get; set; }
    public decimal? AnnualRevenue { get; set; }
    public byte? FiscalYearEndMonth { get; set; }
    public string? EntityStructure { get; set; }
    public bool ProfileCompleted { get; set; }
    public DateTime? ProfileCompletedAt { get; set; }
    public List<OrgNaicsDto> NaicsCodes { get; set; } = new();
    public List<OrgCertificationDto> Certifications { get; set; } = new();
}
