using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IExpiringContractService
{
    Task<List<ExpiringContractDto>> GetExpiringContractsAsync(int orgId, ExpiringContractSearchRequest request);
}
