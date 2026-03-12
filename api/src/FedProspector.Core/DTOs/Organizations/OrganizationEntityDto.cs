namespace FedProspector.Core.DTOs.Organizations;

public class OrganizationEntityDto
{
    public int Id { get; set; }
    public string UeiSam { get; set; } = string.Empty;
    public string Relationship { get; set; } = string.Empty;
    public bool IsActive { get; set; }
    public string? Notes { get; set; }
    public string? AddedByName { get; set; }
    public DateTime CreatedAt { get; set; }

    // Entity details
    public string? LegalBusinessName { get; set; }
    public string? DbaName { get; set; }
    public string? CageCode { get; set; }
    public string? RegistrationStatus { get; set; }
    public string? PrimaryNaics { get; set; }
    public int NaicsCount { get; set; }
    public int CertificationCount { get; set; }
}

public class LinkEntityRequest
{
    public string UeiSam { get; set; } = string.Empty;
    public string Relationship { get; set; } = "SELF";
    public string? Notes { get; set; }
}

public class RefreshSelfEntityResponse
{
    public int NaicsCopied { get; set; }
    public int CertificationsCopied { get; set; }
    public bool ProfileUpdated { get; set; }
    public string Message { get; set; } = string.Empty;
}
