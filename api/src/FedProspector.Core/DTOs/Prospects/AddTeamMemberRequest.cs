namespace FedProspector.Core.DTOs.Prospects;

public class AddTeamMemberRequest
{
    public string? UeiSam { get; set; }
    public string Role { get; set; } = string.Empty;
    public string? Notes { get; set; }
    public decimal? ProposedHourlyRate { get; set; }
    public decimal? CommitmentPct { get; set; }
}
