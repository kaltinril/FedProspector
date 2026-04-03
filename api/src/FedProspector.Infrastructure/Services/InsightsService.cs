using FedProspector.Core.DTOs.Insights;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using MySqlConnector;

namespace FedProspector.Infrastructure.Services;

public class InsightsService : IInsightsService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<InsightsService> _logger;

    public InsightsService(FedProspectorDbContext context, ILogger<InsightsService> logger)
    {
        _context = context;
        _logger = logger;
    }

    /// <summary>
    /// Find similar opportunities by NAICS/agency/set-aside/PSC matching.
    /// Uses raw SQL with WHERE pushed into query for performance (MySQL can't
    /// push predicates into the view efficiently).
    /// </summary>
    public async Task<List<SimilarOpportunityDto>> GetSimilarOpportunitiesAsync(string noticeId, int maxResults = 20)
    {
        if (maxResults < 1) maxResults = 1;
        if (maxResults > 100) maxResults = 100;

        const string sql = """
            SELECT
                src.notice_id                                     AS source_notice_id,
                m.notice_id                                       AS match_notice_id,
                m.title                                           AS match_title,
                m.department_name                                 AS match_agency,
                m.naics_code                                      AS match_naics,
                m.set_aside_code                                  AS match_set_aside,
                COALESCE(m.estimated_contract_value, m.award_amount) AS match_value,
                m.posted_date                                     AS match_posted_date,
                m.response_deadline                               AS match_response_deadline,
                CONCAT_WS(', ',
                    IF(src.naics_code IS NOT NULL
                       AND src.naics_code = m.naics_code,         'NAICS', NULL),
                    IF(src.department_name IS NOT NULL
                       AND src.department_name = m.department_name, 'AGENCY', NULL),
                    IF(src.set_aside_code IS NOT NULL
                       AND src.set_aside_code != ''
                       AND src.set_aside_code = m.set_aside_code, 'SET_ASIDE', NULL),
                    IF(src.classification_code IS NOT NULL
                       AND src.classification_code = m.classification_code, 'PSC', NULL)
                )                                                 AS similarity_factors,
                (
                    (src.naics_code IS NOT NULL AND src.naics_code = m.naics_code) * 40
                  + (src.department_name IS NOT NULL AND src.department_name = m.department_name) * 25
                  + (src.set_aside_code IS NOT NULL AND src.set_aside_code != ''
                     AND src.set_aside_code = m.set_aside_code) * 20
                  + (src.classification_code IS NOT NULL AND src.classification_code = m.classification_code) * 15
                )                                                 AS similarity_score
            FROM opportunity src
            INNER JOIN opportunity m
                ON m.notice_id != src.notice_id
                AND m.active = 'Y'
                AND (
                    (src.naics_code IS NOT NULL AND src.naics_code = m.naics_code)
                    OR (src.department_name IS NOT NULL AND src.department_name = m.department_name)
                    OR (src.set_aside_code IS NOT NULL AND src.set_aside_code != ''
                        AND src.set_aside_code = m.set_aside_code)
                )
            WHERE src.notice_id = @noticeId
            ORDER BY similarity_score DESC
            LIMIT @maxResults
            """;

        var rows = await _context.SimilarOpportunities
            .FromSqlRaw(sql,
                new MySqlParameter("@noticeId", noticeId),
                new MySqlParameter("@maxResults", maxResults))
            .AsNoTracking()
            .ToListAsync();

        return rows.Select(r => new SimilarOpportunityDto
        {
            MatchNoticeId = r.MatchNoticeId,
            MatchTitle = r.MatchTitle,
            MatchAgency = r.MatchAgency,
            MatchNaics = r.MatchNaics,
            MatchSetAside = r.MatchSetAside,
            MatchValue = r.MatchValue,
            MatchPostedDate = r.MatchPostedDate,
            MatchResponseDeadline = r.MatchResponseDeadline,
            SimilarityFactors = r.SimilarityFactors,
            SimilarityScore = r.SimilarityScore
        }).ToList();
    }

    public async Task<List<CrossSourceValidationDto>> GetCrossSourceValidationAsync()
    {
        var rows = await _context.CrossSourceValidations
            .AsNoTracking()
            .ToListAsync();

        return rows.Select(r => new CrossSourceValidationDto
        {
            CheckId = r.CheckId,
            CheckName = r.CheckName,
            SourceAName = r.SourceAName,
            SourceACount = r.SourceACount,
            SourceBName = r.SourceBName,
            SourceBCount = r.SourceBCount,
            Difference = r.Difference,
            PctDifference = r.PctDifference,
            Status = r.Status
        }).ToList();
    }

    public async Task<List<DataFreshnessDto>> GetDataFreshnessAsync()
    {
        var rows = await _context.DataFreshness
            .AsNoTracking()
            .ToListAsync();

        return rows.Select(r => new DataFreshnessDto
        {
            SourceName = r.SourceName,
            LastLoadDate = r.LastLoadDate,
            RecordsLoaded = r.RecordsLoaded,
            LastLoadStatus = r.LastLoadStatus,
            HoursSinceLastLoad = r.HoursSinceLastLoad,
            FreshnessStatus = r.FreshnessStatus,
            TableRowCount = r.TableRowCount,
            TableName = r.TableName
        }).ToList();
    }

    public async Task<List<DataCompletenessDto>> GetDataCompletenessAsync()
    {
        var rows = await _context.DataCompleteness
            .AsNoTracking()
            .ToListAsync();

        return rows.Select(r => new DataCompletenessDto
        {
            TableName = r.TableName,
            TotalRows = r.TotalRows,
            FieldName = r.FieldName,
            NonNullCount = r.NonNullCount,
            NullCount = r.NullCount,
            CompletenessPct = r.CompletenessPct
        }).ToList();
    }

    public async Task<DataQualityDashboardDto> GetDataQualityDashboardAsync()
    {
        var freshnessTask = GetDataFreshnessAsync();
        var completenessTask = GetDataCompletenessAsync();
        var validationTask = GetCrossSourceValidationAsync();

        await Task.WhenAll(freshnessTask, completenessTask, validationTask);

        return new DataQualityDashboardDto
        {
            Freshness = await freshnessTask,
            Completeness = await completenessTask,
            Validation = await validationTask
        };
    }

    public async Task<List<ProspectCompetitorSummaryDto>> GetProspectCompetitorSummariesAsync(
        int organizationId, int[] prospectIds)
    {
        if (prospectIds.Length == 0)
            return [];

        var rows = await _context.ProspectCompetitorSummaries
            .AsNoTracking()
            .Where(r => r.OrganizationId == organizationId && prospectIds.Contains(r.ProspectId))
            .ToListAsync();

        return rows.Select(MapCompetitorSummary).ToList();
    }

    public async Task<ProspectCompetitorSummaryDto?> GetProspectCompetitorSummaryAsync(int prospectId)
    {
        var row = await _context.ProspectCompetitorSummaries
            .AsNoTracking()
            .FirstOrDefaultAsync(r => r.ProspectId == prospectId);

        return row != null ? MapCompetitorSummary(row) : null;
    }

    private static ProspectCompetitorSummaryDto MapCompetitorSummary(Core.Models.Views.ProspectCompetitorSummaryView r)
    {
        return new ProspectCompetitorSummaryDto
        {
            ProspectId = r.ProspectId,
            NoticeId = r.NoticeId,
            OpportunityTitle = r.OpportunityTitle,
            NaicsCode = r.NaicsCode,
            DepartmentName = r.DepartmentName,
            SetAsideCode = r.SetAsideCode,
            LikelyIncumbent = r.LikelyIncumbent,
            IncumbentUei = r.IncumbentUei,
            IncumbentContractValue = r.IncumbentContractValue,
            IncumbentContractEnd = r.IncumbentContractEnd,
            EstimatedCompetitorCount = r.EstimatedCompetitorCount
        };
    }
}
