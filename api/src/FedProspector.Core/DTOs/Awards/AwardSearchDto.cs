namespace FedProspector.Core.DTOs.Awards;

public class AwardSearchDto
{
    public string ContractId { get; set; } = string.Empty;
    public string? SolicitationNumber { get; set; }
    public string? AgencyName { get; set; }
    public string? ContractingOfficeName { get; set; }
    public string? VendorName { get; set; }
    public string? VendorUei { get; set; }
    public DateOnly? DateSigned { get; set; }
    public DateOnly? EffectiveDate { get; set; }
    public DateOnly? CompletionDate { get; set; }
    public decimal? DollarsObligated { get; set; }
    public decimal? BaseAndAllOptions { get; set; }
    public string? NaicsCode { get; set; }
    public string? NaicsDescription { get; set; }
    public string? PscCode { get; set; }
    public string? PscDescription { get; set; }
    public string? SetAsideType { get; set; }
    public string? SetAsideDescription { get; set; }
    public string? SetAsideCategory { get; set; }
    public string? TypeOfContract { get; set; }
    public int? NumberOfOffers { get; set; }
    public string? ExtentCompeted { get; set; }
    public string? Description { get; set; }
    public string? DataSource { get; set; }
}
