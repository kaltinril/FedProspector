using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Subawards;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using MySqlConnector;

namespace FedProspector.Infrastructure.Services;

public class SubawardService : ISubawardService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<SubawardService> _logger;

    public SubawardService(FedProspectorDbContext context, ILogger<SubawardService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<PagedResponse<TeamingPartnerDto>> GetTeamingPartnersAsync(TeamingPartnerSearchRequest request)
    {
        var offset = (request.Page - 1) * request.PageSize;

        // Build WHERE conditions dynamically
        var conditions = new List<string>();
        var sqlParams = new List<MySqlParameter>();

        if (!string.IsNullOrWhiteSpace(request.Naics))
        {
            conditions.Add("s.naics_code = @naics");
            sqlParams.Add(new MySqlParameter("@naics", request.Naics));
        }

        if (!string.IsNullOrWhiteSpace(request.PrimeUei))
        {
            conditions.Add("s.prime_uei = @primeUei");
            sqlParams.Add(new MySqlParameter("@primeUei", request.PrimeUei));
        }

        if (!string.IsNullOrWhiteSpace(request.SubUei))
        {
            conditions.Add("s.sub_uei = @subUei");
            sqlParams.Add(new MySqlParameter("@subUei", request.SubUei));
        }

        var whereClause = conditions.Count > 0 ? "WHERE " + string.Join(" AND ", conditions) : "";

        sqlParams.Add(new MySqlParameter("@minSubs", request.MinSubawards));
        sqlParams.Add(new MySqlParameter("@limit", request.PageSize));
        sqlParams.Add(new MySqlParameter("@offset", offset));

        // Main query
        var dataSql = $@"
            SELECT
                s.prime_uei AS PrimeUei,
                s.prime_name AS PrimeName,
                COUNT(*) AS SubCount,
                CAST(SUM(s.sub_amount) AS DECIMAL(15,2)) AS TotalSubAmount,
                COUNT(DISTINCT s.sub_uei) AS UniqueSubs,
                GROUP_CONCAT(DISTINCT s.naics_code ORDER BY s.naics_code SEPARATOR ', ') AS NaicsCodes
            FROM sam_subaward s
            {whereClause}
            GROUP BY s.prime_uei, s.prime_name
            HAVING COUNT(*) >= @minSubs
            ORDER BY SubCount DESC
            LIMIT @limit OFFSET @offset";

        // Count query
        var countSql = $@"
            SELECT COUNT(*) FROM (
                SELECT s.prime_uei
                FROM sam_subaward s
                {whereClause}
                GROUP BY s.prime_uei, s.prime_name
                HAVING COUNT(*) >= @minSubs
            ) AS grouped";

        // Execute both queries using raw ADO.NET for reliable parameterization
        var connection = _context.Database.GetDbConnection();
        try
        {
            await _context.Database.OpenConnectionAsync();
            // Count
            int totalCount;
            using (var countCmd = connection.CreateCommand())
            {
                countCmd.CommandText = countSql;
                foreach (var p in sqlParams.Where(p => p.ParameterName != "@limit" && p.ParameterName != "@offset"))
                    countCmd.Parameters.Add(p.Clone());
                var result = await countCmd.ExecuteScalarAsync();
                totalCount = Convert.ToInt32(result);
            }

            // Data
            var items = new List<TeamingPartnerDto>();
            using (var dataCmd = connection.CreateCommand())
            {
                dataCmd.CommandText = dataSql;
                foreach (var p in sqlParams)
                    dataCmd.Parameters.Add(p.Clone());
                using var reader = await dataCmd.ExecuteReaderAsync();
                while (await reader.ReadAsync())
                {
                    items.Add(new TeamingPartnerDto
                    {
                        PrimeUei = reader.IsDBNull(0) ? null : reader.GetString(0),
                        PrimeName = reader.IsDBNull(1) ? null : reader.GetString(1),
                        SubCount = reader.GetInt32(2),
                        TotalSubAmount = reader.IsDBNull(3) ? null : reader.GetDecimal(3),
                        UniqueSubs = reader.GetInt32(4),
                        NaicsCodes = reader.IsDBNull(5) ? null : reader.GetString(5)
                    });
                }
            }

            return new PagedResponse<TeamingPartnerDto>
            {
                Items = items,
                Page = request.Page,
                PageSize = request.PageSize,
                TotalCount = totalCount
            };
        }
        finally
        {
            await _context.Database.CloseConnectionAsync();
        }
    }
}
