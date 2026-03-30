using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IAttachmentIntelService
{
    Task<DocumentIntelligenceDto?> GetDocumentIntelligenceAsync(string noticeId);
    Task<LoadRequestStatusDto> RequestAnalysisAsync(string noticeId, string tier, int? userId);
    Task<LoadRequestStatusDto?> GetAnalysisStatusAsync(string noticeId);
    Task<AnalysisEstimateDto> GetAnalysisEstimateAsync(string noticeId, string model = "haiku");
    Task<OpportunityIdentifiersDto> GetIdentifierRefsAsync(string noticeId);
}
