using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IQualificationService
{
    Task<QualificationCheckDto> CheckQualificationAsync(string noticeId, int orgId);
}
