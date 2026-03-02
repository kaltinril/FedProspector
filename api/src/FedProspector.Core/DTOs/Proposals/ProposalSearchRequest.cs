namespace FedProspector.Core.DTOs.Proposals;

public class ProposalSearchRequest : PagedRequest
{
    public string? Status { get; set; }
    public int? ProspectId { get; set; }
}
