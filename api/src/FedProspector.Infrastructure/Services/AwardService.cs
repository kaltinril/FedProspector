using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class AwardService : IAwardService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<AwardService> _logger;

    public AwardService(FedProspectorDbContext context, ILogger<AwardService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<PagedResponse<AwardSearchDto>> SearchAsync(AwardSearchRequest request)
    {
        var query = _context.FpdsContracts.AsNoTracking().AsQueryable();

        // Base awards only unless searching by PIID (show all modifications)
        if (string.IsNullOrWhiteSpace(request.Piid))
            query = query.Where(c => c.ModificationNumber == "0");

        // Apply filters
        if (!string.IsNullOrWhiteSpace(request.Piid))
            query = query.Where(c => c.ContractId == request.Piid);

        if (!string.IsNullOrWhiteSpace(request.Solicitation))
            query = query.Where(c => c.SolicitationNumber == request.Solicitation);

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(c => c.NaicsCode == request.Naics);

        if (!string.IsNullOrWhiteSpace(request.Agency))
        {
            var escapedAgency = EscapeLikePattern(request.Agency);
            query = query.Where(c => c.AgencyId == request.Agency
                || (c.AgencyName != null && EF.Functions.Like(c.AgencyName, $"%{escapedAgency}%")));
        }

        if (!string.IsNullOrWhiteSpace(request.VendorUei))
            query = query.Where(c => c.VendorUei == request.VendorUei);

        if (!string.IsNullOrWhiteSpace(request.VendorName))
        {
            var escapedVendor = EscapeLikePattern(request.VendorName);
            query = query.Where(c => c.VendorName != null && EF.Functions.Like(c.VendorName, $"%{escapedVendor}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.SetAside))
            query = query.Where(c => c.SetAsideType == request.SetAside);

        if (request.MinValue.HasValue)
            query = query.Where(c => c.BaseAndAllOptions >= request.MinValue);

        if (request.MaxValue.HasValue)
            query = query.Where(c => c.BaseAndAllOptions <= request.MaxValue);

        if (request.DateFrom.HasValue)
            query = query.Where(c => c.DateSigned >= request.DateFrom);

        if (request.DateTo.HasValue)
            query = query.Where(c => c.DateSigned <= request.DateTo);

        var totalCount = await query.CountAsync();

        // Default sort: DateSigned descending (most recent first)
        IOrderedQueryable<Core.Models.FpdsContract> ordered = query.OrderByDescending(c => c.DateSigned);

        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            ordered = request.SortBy.ToLowerInvariant() switch
            {
                "datesigned" => request.SortDescending ? query.OrderByDescending(c => c.DateSigned) : query.OrderBy(c => c.DateSigned),
                "baseandalloptionsvalue" or "value" => request.SortDescending ? query.OrderByDescending(c => c.BaseAndAllOptions) : query.OrderBy(c => c.BaseAndAllOptions),
                "vendorname" => request.SortDescending ? query.OrderByDescending(c => c.VendorName) : query.OrderBy(c => c.VendorName),
                "agencyname" => request.SortDescending ? query.OrderByDescending(c => c.AgencyName) : query.OrderBy(c => c.AgencyName),
                _ => ordered
            };
        }

        var results = await ordered
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .Select(c => new AwardSearchDto
            {
                ContractId = c.ContractId,
                SolicitationNumber = c.SolicitationNumber,
                AgencyName = c.AgencyName,
                ContractingOfficeName = c.ContractingOfficeName,
                VendorName = c.VendorName,
                VendorUei = c.VendorUei,
                DateSigned = c.DateSigned,
                EffectiveDate = c.EffectiveDate,
                CompletionDate = c.CompletionDate,
                DollarsObligated = c.DollarsObligated,
                BaseAndAllOptions = c.BaseAndAllOptions,
                NaicsCode = c.NaicsCode,
                PscCode = c.PscCode,
                SetAsideType = c.SetAsideType,
                TypeOfContract = c.TypeOfContract,
                NumberOfOffers = c.NumberOfOffers,
                ExtentCompeted = c.ExtentCompeted,
                Description = c.Description,
                DataSource = "fpds"
            })
            .ToListAsync();

        // Fallback: if FPDS returned fewer results than page size, supplement with USASpending
        if (results.Count < request.PageSize)
        {
            var fpdsPoiids = results.Select(r => r.ContractId).ToHashSet();
            var usaResults = await SearchUsaspendingAsync(request, request.PageSize - results.Count, fpdsPoiids);
            results.AddRange(usaResults);
            // Adjust total count
            totalCount += await CountUsaspendingAsync(request, fpdsPoiids);
        }

        return new PagedResponse<AwardSearchDto>
        {
            Items = results,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public async Task<AwardDetailResponse> GetDetailAsync(string contractId)
    {
        // Fetch base award (modification_number = '0') from FPDS
        var contract = await _context.FpdsContracts.AsNoTracking()
            .FirstOrDefaultAsync(c => c.ContractId == contractId && c.ModificationNumber == "0");

        // Fetch USASpending award by Piid
        var usaAward = await _context.UsaspendingAwards.AsNoTracking()
            .FirstOrDefaultAsync(a => a.Piid == contractId);

        // Fetch transactions if USASpending award exists
        var transactions = new List<TransactionDto>();
        if (usaAward != null)
        {
            transactions = await _context.UsaspendingTransactions.AsNoTracking()
                .Where(t => t.AwardId == usaAward.GeneratedUniqueAwardId)
                .OrderBy(t => t.ActionDate)
                .Select(t => new TransactionDto
                {
                    ActionDate = t.ActionDate,
                    ModificationNumber = t.ModificationNumber,
                    ActionType = t.ActionType,
                    ActionTypeDescription = t.ActionTypeDescription,
                    FederalActionObligation = t.FederalActionObligation,
                    Description = t.Description
                })
                .ToListAsync();
        }

        // Fetch most recent load request for this PIID
        var loadRequest = await _context.DataLoadRequests.AsNoTracking()
            .Where(r => r.LookupKey == contractId)
            .OrderByDescending(r => r.RequestedAt)
            .FirstOrDefaultAsync();

        var hasFpds = contract != null;
        var hasUsa = usaAward != null;

        // Determine data status
        string dataStatus;
        if (hasFpds)
            dataStatus = "full"; // FPDS is primary source — full regardless of USASpending
        else if (hasUsa)
            dataStatus = "partial"; // Only USASpending, no FPDS
        else
            dataStatus = "not_loaded";

        // Build detail DTO
        AwardDetailDto? detail = null;

        if (hasFpds)
        {
            // Full detail from FPDS contract
            VendorSummaryDto? vendorProfile = null;
            if (!string.IsNullOrWhiteSpace(contract!.VendorUei))
            {
                var entity = await _context.Entities.AsNoTracking()
                    .FirstOrDefaultAsync(e => e.UeiSam == contract.VendorUei);

                if (entity != null)
                {
                    vendorProfile = new VendorSummaryDto
                    {
                        UeiSam = entity.UeiSam,
                        LegalBusinessName = entity.LegalBusinessName,
                        DbaName = entity.DbaName,
                        RegistrationStatus = entity.RegistrationStatus,
                        PrimaryNaics = entity.PrimaryNaics,
                        EntityUrl = entity.EntityUrl
                    };
                }
            }

            detail = new AwardDetailDto
            {
                ContractId = contract.ContractId,
                IdvPiid = contract.IdvPiid,
                AgencyId = contract.AgencyId,
                AgencyName = contract.AgencyName,
                ContractingOfficeId = contract.ContractingOfficeId,
                ContractingOfficeName = contract.ContractingOfficeName,
                FundingAgencyId = contract.FundingAgencyId,
                FundingAgencyName = contract.FundingAgencyName,
                VendorUei = contract.VendorUei,
                VendorName = contract.VendorName,
                DateSigned = contract.DateSigned,
                EffectiveDate = contract.EffectiveDate,
                CompletionDate = contract.CompletionDate,
                UltimateCompletionDate = contract.UltimateCompletionDate,
                LastModifiedDate = contract.LastModifiedDate,
                DollarsObligated = contract.DollarsObligated,
                BaseAndAllOptions = contract.BaseAndAllOptions,
                NaicsCode = contract.NaicsCode,
                PscCode = contract.PscCode,
                SetAsideType = contract.SetAsideType,
                TypeOfContract = contract.TypeOfContract,
                TypeOfContractPricing = contract.TypeOfContractPricing,
                Description = contract.Description,
                PopState = contract.PopState,
                PopCountry = contract.PopCountry,
                PopZip = contract.PopZip,
                ExtentCompeted = contract.ExtentCompeted,
                NumberOfOffers = contract.NumberOfOffers,
                SolicitationNumber = contract.SolicitationNumber,
                SolicitationDate = contract.SolicitationDate,
                Transactions = transactions,
                VendorProfile = vendorProfile
            };
        }
        else if (hasUsa)
        {
            // Partial detail from USASpending award
            VendorSummaryDto? vendorProfile = null;
            if (!string.IsNullOrWhiteSpace(usaAward!.RecipientUei))
            {
                var entity = await _context.Entities.AsNoTracking()
                    .FirstOrDefaultAsync(e => e.UeiSam == usaAward.RecipientUei);

                if (entity != null)
                {
                    vendorProfile = new VendorSummaryDto
                    {
                        UeiSam = entity.UeiSam,
                        LegalBusinessName = entity.LegalBusinessName,
                        DbaName = entity.DbaName,
                        RegistrationStatus = entity.RegistrationStatus,
                        PrimaryNaics = entity.PrimaryNaics,
                        EntityUrl = entity.EntityUrl
                    };
                }
            }

            detail = new AwardDetailDto
            {
                ContractId = contractId,
                VendorName = usaAward.RecipientName,
                VendorUei = usaAward.RecipientUei,
                DollarsObligated = usaAward.TotalObligation,
                BaseAndAllOptions = usaAward.BaseAndAllOptionsValue,
                AgencyName = usaAward.AwardingAgencyName,
                FundingAgencyName = usaAward.FundingAgencyName,
                NaicsCode = usaAward.NaicsCode,
                PscCode = usaAward.PscCode,
                SetAsideType = usaAward.TypeOfSetAside,
                Description = usaAward.AwardDescription,
                PopState = usaAward.PopState,
                PopCountry = usaAward.PopCountry,
                PopZip = usaAward.PopZip,
                Transactions = transactions,
                VendorProfile = vendorProfile
            };
        }

        // Build load status
        LoadRequestStatusDto? loadStatus = null;
        if (loadRequest != null)
        {
            loadStatus = new LoadRequestStatusDto
            {
                RequestId = loadRequest.RequestId,
                RequestType = loadRequest.RequestType,
                Status = loadRequest.Status,
                RequestedAt = loadRequest.RequestedAt,
                ErrorMessage = loadRequest.ErrorMessage
            };
        }

        return new AwardDetailResponse
        {
            ContractId = contractId,
            DataStatus = dataStatus,
            HasFpdsData = hasFpds,
            HasUsaspendingData = hasUsa,
            Detail = detail,
            LoadStatus = loadStatus
        };
    }

    public async Task<BurnRateDto?> GetBurnRateAsync(string contractId)
    {
        // Find USASpending award by Piid
        var usaAward = await _context.UsaspendingAwards.AsNoTracking()
            .FirstOrDefaultAsync(a => a.Piid == contractId);

        if (usaAward == null) return null;

        // Get monthly spend breakdown using raw SQL for GROUP BY with DATE_FORMAT
        var awardId = usaAward.GeneratedUniqueAwardId;
        var monthlyData = await _context.Database
            .SqlQueryRaw<MonthlySpendDto>(
                "SELECT DATE_FORMAT(action_date, '%Y-%m') AS year_month, " +
                "SUM(federal_action_obligation) AS amount, " +
                "COUNT(*) AS transaction_count " +
                "FROM usaspending_transaction " +
                "WHERE award_id = {0} AND federal_action_obligation IS NOT NULL " +
                "GROUP BY DATE_FORMAT(action_date, '%Y-%m') " +
                "ORDER BY year_month",
                awardId)
            .ToListAsync();

        if (monthlyData.Count == 0)
        {
            return new BurnRateDto
            {
                ContractId = contractId,
                TotalObligated = usaAward.TotalObligation ?? 0m,
                BaseAndAllOptions = usaAward.BaseAndAllOptionsValue,
                PercentSpent = null,
                MonthsElapsed = 0,
                MonthlyRate = 0m,
                TransactionCount = 0,
                MonthlyBreakdown = []
            };
        }

        // Calculate months elapsed (inclusive)
        var first = monthlyData.First();
        var last = monthlyData.Last();
        var firstParts = first.YearMonth.Split('-');
        var lastParts = last.YearMonth.Split('-');
        int fy = int.Parse(firstParts[0]), fm = int.Parse(firstParts[1]);
        int ly = int.Parse(lastParts[0]), lm = int.Parse(lastParts[1]);
        int monthsElapsed = (ly - fy) * 12 + (lm - fm) + 1;

        var totalObligated = usaAward.TotalObligation ?? 0m;
        var totalTransactions = monthlyData.Sum(m => m.TransactionCount);
        var monthlyRate = monthsElapsed > 0 ? totalObligated / monthsElapsed : 0m;

        decimal? percentSpent = null;
        if (usaAward.BaseAndAllOptionsValue.HasValue && usaAward.BaseAndAllOptionsValue.Value != 0m)
        {
            percentSpent = Math.Round(totalObligated / usaAward.BaseAndAllOptionsValue.Value * 100m, 2);
        }

        return new BurnRateDto
        {
            ContractId = contractId,
            TotalObligated = totalObligated,
            BaseAndAllOptions = usaAward.BaseAndAllOptionsValue,
            PercentSpent = percentSpent,
            MonthsElapsed = monthsElapsed,
            MonthlyRate = Math.Round(monthlyRate, 2),
            TransactionCount = totalTransactions,
            MonthlyBreakdown = monthlyData
        };
    }

    public async Task<List<MarketShareDto>> GetMarketShareAsync(string naicsCode, int limit = 10)
    {
        var results = await _context.Database
            .SqlQueryRaw<MarketShareDto>(
                "SELECT MAX(vendor_name) AS vendor_name, vendor_uei AS vendor_uei, " +
                "COUNT(*) AS award_count, " +
                "SUM(base_and_all_options) AS total_value, " +
                "AVG(base_and_all_options) AS average_value, " +
                "MAX(date_signed) AS last_award_date " +
                "FROM fpds_contract " +
                "WHERE naics_code = {0} AND vendor_uei IS NOT NULL AND vendor_uei != '' " +
                "AND modification_number = '0' " +
                "GROUP BY vendor_uei " +
                "ORDER BY TotalValue DESC " +
                "LIMIT {1}",
                naicsCode, limit)
            .ToListAsync();

        return results;
    }

    public async Task<LoadRequestStatusDto> RequestLoadAsync(string contractId, string tier, int? userId)
    {
        // Map tier to request_type
        var requestType = tier.ToLowerInvariant() switch
        {
            "fpds" => "FPDS_AWARD",
            _ => "USASPENDING_AWARD"
        };

        // Check for existing pending/processing request
        var existing = await _context.DataLoadRequests.FirstOrDefaultAsync(r =>
            r.LookupKey == contractId &&
            r.RequestType == requestType &&
            (r.Status == "PENDING" || r.Status == "PROCESSING"));

        if (existing != null)
        {
            return new LoadRequestStatusDto
            {
                RequestId = existing.RequestId,
                RequestType = existing.RequestType,
                Status = existing.Status,
                RequestedAt = existing.RequestedAt,
                ErrorMessage = existing.ErrorMessage
            };
        }

        // Create new request
        var request = new DataLoadRequest
        {
            RequestType = requestType,
            LookupKey = contractId,
            LookupKeyType = "PIID",
            Status = "PENDING",
            RequestedBy = userId,
            RequestedAt = DateTime.UtcNow
        };

        _context.DataLoadRequests.Add(request);
        await _context.SaveChangesAsync();

        return new LoadRequestStatusDto
        {
            RequestId = request.RequestId,
            RequestType = request.RequestType,
            Status = request.Status,
            RequestedAt = request.RequestedAt
        };
    }

    public async Task<LoadRequestStatusDto?> GetLoadStatusAsync(string contractId)
    {
        var request = await _context.DataLoadRequests.AsNoTracking()
            .Where(r => r.LookupKey == contractId)
            .OrderByDescending(r => r.RequestedAt)
            .FirstOrDefaultAsync();

        if (request == null) return null;

        return new LoadRequestStatusDto
        {
            RequestId = request.RequestId,
            RequestType = request.RequestType,
            Status = request.Status,
            RequestedAt = request.RequestedAt,
            ErrorMessage = request.ErrorMessage
        };
    }

    private async Task<List<AwardSearchDto>> SearchUsaspendingAsync(
        AwardSearchRequest request, int limit, HashSet<string> excludePiids)
    {
        var query = BuildUsaspendingQuery(request, excludePiids);

        // Apply sort consistent with FPDS query
        IOrderedQueryable<UsaspendingAward> ordered = query.OrderByDescending(ua => ua.StartDate);

        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            ordered = request.SortBy.ToLowerInvariant() switch
            {
                "datesigned" => request.SortDescending ? query.OrderByDescending(ua => ua.StartDate) : query.OrderBy(ua => ua.StartDate),
                "baseandalloptionsvalue" or "value" => request.SortDescending ? query.OrderByDescending(ua => ua.BaseAndAllOptionsValue) : query.OrderBy(ua => ua.BaseAndAllOptionsValue),
                "vendorname" => request.SortDescending ? query.OrderByDescending(ua => ua.RecipientName) : query.OrderBy(ua => ua.RecipientName),
                "agencyname" => request.SortDescending ? query.OrderByDescending(ua => ua.AwardingAgencyName) : query.OrderBy(ua => ua.AwardingAgencyName),
                _ => ordered
            };
        }

        return await ordered
            .Take(limit)
            .Select(ua => new AwardSearchDto
            {
                ContractId = ua.Piid!,
                SolicitationNumber = ua.SolicitationIdentifier,
                AgencyName = ua.AwardingAgencyName,
                ContractingOfficeName = null,
                VendorName = ua.RecipientName,
                VendorUei = ua.RecipientUei,
                DateSigned = ua.StartDate,
                EffectiveDate = null,
                CompletionDate = null,
                DollarsObligated = ua.TotalObligation,
                BaseAndAllOptions = ua.BaseAndAllOptionsValue,
                NaicsCode = ua.NaicsCode,
                PscCode = ua.PscCode,
                SetAsideType = ua.TypeOfSetAside,
                TypeOfContract = null,
                NumberOfOffers = null,
                ExtentCompeted = null,
                Description = ua.AwardDescription,
                DataSource = "usaspending"
            })
            .ToListAsync();
    }

    private async Task<int> CountUsaspendingAsync(
        AwardSearchRequest request, HashSet<string> excludePiids)
    {
        return await BuildUsaspendingQuery(request, excludePiids).CountAsync();
    }

    private IQueryable<UsaspendingAward> BuildUsaspendingQuery(
        AwardSearchRequest request, HashSet<string> excludePiids)
    {
        var query = _context.UsaspendingAwards.AsNoTracking()
            .Where(ua => ua.Piid != null);

        if (excludePiids.Count > 0)
            query = query.Where(ua => !excludePiids.Contains(ua.Piid!));

        if (!string.IsNullOrWhiteSpace(request.Piid))
            query = query.Where(ua => ua.Piid!.Contains(request.Piid));

        if (!string.IsNullOrWhiteSpace(request.Solicitation))
            query = query.Where(ua => ua.SolicitationIdentifier != null && ua.SolicitationIdentifier.Contains(request.Solicitation));

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(ua => ua.NaicsCode == request.Naics);

        if (!string.IsNullOrWhiteSpace(request.Agency))
        {
            var escapedAgency = EscapeLikePattern(request.Agency);
            query = query.Where(ua => ua.AwardingAgencyName != null && EF.Functions.Like(ua.AwardingAgencyName, $"%{escapedAgency}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.VendorUei))
            query = query.Where(ua => ua.RecipientUei == request.VendorUei);

        if (!string.IsNullOrWhiteSpace(request.VendorName))
        {
            var escapedVendor = EscapeLikePattern(request.VendorName);
            query = query.Where(ua => ua.RecipientName != null && EF.Functions.Like(ua.RecipientName, $"%{escapedVendor}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.SetAside))
            query = query.Where(ua => ua.TypeOfSetAside == request.SetAside);

        if (request.MinValue.HasValue)
            query = query.Where(ua => ua.BaseAndAllOptionsValue >= request.MinValue);

        if (request.MaxValue.HasValue)
            query = query.Where(ua => ua.BaseAndAllOptionsValue <= request.MaxValue);

        if (request.DateFrom.HasValue)
            query = query.Where(ua => ua.StartDate >= request.DateFrom);

        if (request.DateTo.HasValue)
            query = query.Where(ua => ua.StartDate <= request.DateTo);

        return query;
    }

    /// <summary>
    /// Escapes LIKE special characters (%, _, \) so user input is treated as literals.
    /// </summary>
    private static string EscapeLikePattern(string input)
    {
        if (string.IsNullOrEmpty(input)) return input;
        return input.Replace("\\", "\\\\").Replace("%", "\\%").Replace("_", "\\_");
    }
}
