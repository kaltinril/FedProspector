namespace FedProspector.Core.DTOs.Prospects;

public class ProspectTeamMemberDto
{
    public int Id { get; set; }
    public string? UeiSam { get; set; }
    public string? EntityName { get; set; }
    public string? Role { get; set; }
    public string? Notes { get; set; }
    public decimal? ProposedHourlyRate { get; set; }
    public decimal? CommitmentPct { get; set; }
}
