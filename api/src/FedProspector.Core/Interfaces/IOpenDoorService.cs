using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IOpenDoorService
{
    /// <summary>
    /// Score a specific prime contractor's small business engagement.
    /// </summary>
    Task<OpenDoorScoreDto> ScorePrimeAsync(string primeUei, int years = 3);

    /// <summary>
    /// Find primes with best Open Door scores in a NAICS code.
    /// </summary>
    Task<OpenDoorAnalysisDto> FindOpenDoorPrimesAsync(string naicsCode, int years = 3, int limit = 10);
}
