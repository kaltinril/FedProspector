namespace FedProspector.Core.DTOs.Organizations;

public class OrganizationDto
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Slug { get; set; } = string.Empty;
    public bool IsActive { get; set; }
    public int MaxUsers { get; set; }
    public string? SubscriptionTier { get; set; }
    public DateTime CreatedAt { get; set; }
}
