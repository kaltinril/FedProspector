using FedProspector.Core.DTOs.Dashboard;

namespace FedProspector.Core.Interfaces;

public interface IDashboardService
{
    Task<DashboardDto> GetDashboardAsync();
}
