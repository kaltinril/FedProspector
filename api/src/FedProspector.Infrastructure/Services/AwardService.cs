using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.Interfaces;
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
        // Base awards only (modification_number = '0')
        var query = _context.FpdsContracts.AsNoTracking()
            .Where(c => c.ModificationNumber == "0");

        // Apply filters
        if (!string.IsNullOrWhiteSpace(request.Solicitation))
            query = query.Where(c => c.SolicitationNumber == request.Solicitation);

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(c => c.NaicsCode == request.Naics);

        if (!string.IsNullOrWhiteSpace(request.Agency))
            query = query.Where(c => c.AgencyName != null && EF.Functions.Like(c.AgencyName, $"%{request.Agency}%"));

        if (!string.IsNullOrWhiteSpace(request.VendorUei))
            query = query.Where(c => c.VendorUei == request.VendorUei);

        if (!string.IsNullOrWhiteSpace(request.VendorName))
            query = query.Where(c => c.VendorName != null && EF.Functions.Like(c.VendorName, $"%{request.VendorName}%"));

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

        var items = await ordered
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
                Description = c.Description
            })
            .ToListAsync();

        return new PagedResponse<AwardSearchDto>
        {
            Items = items,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public async Task<AwardDetailDto?> GetDetailAsync(string contractId)
    {
        // Fetch base award (modification_number = '0')
        var contract = await _context.FpdsContracts.AsNoTracking()
            .FirstOrDefaultAsync(c => c.ContractId == contractId && c.ModificationNumber == "0");

        if (contract == null) return null;

        // Fetch USASpending transactions: find the award by Piid, then get transactions
        var transactions = new List<TransactionDto>();
        var usaAward = await _context.UsaspendingAwards.AsNoTracking()
            .FirstOrDefaultAsync(a => a.Piid == contractId);

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

        // Fetch vendor entity profile
        VendorSummaryDto? vendorProfile = null;
        if (!string.IsNullOrWhiteSpace(contract.VendorUei))
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

        return new AwardDetailDto
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
                "SELECT DATE_FORMAT(action_date, '%Y-%m') AS YearMonth, " +
                "SUM(federal_action_obligation) AS Amount, " +
                "COUNT(*) AS TransactionCount " +
                "FROM usaspending_transaction " +
                "WHERE award_id = {0} AND federal_action_obligation IS NOT NULL " +
                "GROUP BY DATE_FORMAT(action_date, '%Y-%m') " +
                "ORDER BY YearMonth",
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
}
