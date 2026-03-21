using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IAttachmentIntelService
{
    Task<DocumentIntelligenceDto?> GetDocumentIntelligenceAsync(string noticeId);
    Task<LoadRequestStatusDto> RequestAnalysisAsync(string noticeId, string tier, int? userId);
}
