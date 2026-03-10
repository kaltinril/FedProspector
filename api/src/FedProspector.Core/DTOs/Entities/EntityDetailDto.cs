namespace FedProspector.Core.DTOs.Entities;

public class EntityDetailDto
{
    // Core Entity fields
    public string UeiSam { get; set; } = string.Empty;
    public string? UeiDuns { get; set; }
    public string? CageCode { get; set; }
    public string LegalBusinessName { get; set; } = string.Empty;
    public string? DbaName { get; set; }
    public string? RegistrationStatus { get; set; }
    public DateOnly? InitialRegistrationDate { get; set; }
    public DateOnly? RegistrationExpirationDate { get; set; }
    public DateOnly? LastUpdateDate { get; set; }
    public DateOnly? ActivationDate { get; set; }
    public string? EntityStructureCode { get; set; }
    public string? PrimaryNaics { get; set; }
    public string? EntityUrl { get; set; }
    public string? StateOfIncorporation { get; set; }
    public string? CountryOfIncorporation { get; set; }
    public string? ExclusionStatusFlag { get; set; }
    public string? EftIndicator { get; set; }

    // Nested child collections
    public List<EntityAddressDto> Addresses { get; set; } = [];
    public List<EntityNaicsDto> NaicsCodes { get; set; } = [];
    public List<EntityPscDto> PscCodes { get; set; } = [];
    public List<EntityBusinessTypeDto> BusinessTypes { get; set; } = [];
    public List<EntitySbaCertificationDto> SbaCertifications { get; set; } = [];
    public List<EntityPocDto> PointsOfContact { get; set; } = [];
}

public class EntityAddressDto
{
    public string AddressType { get; set; } = string.Empty;
    public string? AddressLine1 { get; set; }
    public string? AddressLine2 { get; set; }
    public string? City { get; set; }
    public string? StateOrProvince { get; set; }
    public string? ZipCode { get; set; }
    public string? CountryCode { get; set; }
    public string? CountryName { get; set; }
    public string? CongressionalDistrict { get; set; }
}

public class EntityNaicsDto
{
    public string NaicsCode { get; set; } = string.Empty;
    public string? NaicsDescription { get; set; }
    public string? IsPrimary { get; set; }
    public string? SbaSmallBusiness { get; set; }
}

public class EntityPscDto
{
    public string PscCode { get; set; } = string.Empty;
    public string? PscDescription { get; set; }
}

public class EntityBusinessTypeDto
{
    public string BusinessTypeCode { get; set; } = string.Empty;
    public string? BusinessTypeDescription { get; set; }
}

public class EntitySbaCertificationDto
{
    public string? SbaTypeCode { get; set; }
    public string? SbaTypeDesc { get; set; }
    public DateOnly? CertificationEntryDate { get; set; }
    public DateOnly? CertificationExitDate { get; set; }
}

public class EntityPocDto
{
    public string PocType { get; set; } = string.Empty;
    public string? FirstName { get; set; }
    public string? MiddleInitial { get; set; }
    public string? LastName { get; set; }
    public string? Title { get; set; }
    public string? City { get; set; }
    public string? StateOrProvince { get; set; }
    public string? CountryCode { get; set; }
}
