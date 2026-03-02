using FedProspector.Core.DTOs.Admin;

namespace FedProspector.Core.Interfaces;

public interface IAdminService
{
    Task<EtlStatusDto> GetEtlStatusAsync();
}
