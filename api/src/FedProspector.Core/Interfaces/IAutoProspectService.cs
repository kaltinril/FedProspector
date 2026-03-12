using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Interfaces;

public interface IAutoProspectService
{
    Task<AutoProspectResult> GenerateAutoProspectsAsync(int orgId);
    Task<AutoProspectResult> GenerateRecompeteProspectsAsync(int orgId);
}
