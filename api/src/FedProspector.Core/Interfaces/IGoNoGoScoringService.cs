using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Interfaces;

public interface IGoNoGoScoringService
{
    Task<ScoreBreakdownDto> CalculateScoreAsync(int prospectId, int organizationId);
}
