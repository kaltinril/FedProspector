using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Core.Models.Views;
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
        // Resolve vendor UEIs once, shared by both FPDS and USASpending queries.
        // Searches 870K entity rows instead of LIKE on 28M+ award rows.
        HashSet<string>? vendorUeis = null;
        if (!string.IsNullOrWhiteSpace(request.VendorName))
            vendorUeis = await ResolveVendorUeisAsync(request.VendorName);

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

        if (vendorUeis != null)
            query = query.Where(c => c.VendorUei != null && vendorUeis.Contains(c.VendorUei));

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
                "contractid" => request.SortDescending ? query.OrderByDescending(c => c.ContractId) : query.OrderBy(c => c.ContractId),
                "datesigned" => request.SortDescending ? query.OrderByDescending(c => c.DateSigned) : query.OrderBy(c => c.DateSigned),
                "baseandalloptions" or "baseandalloptionsvalue" or "value" => request.SortDescending ? query.OrderByDescending(c => c.BaseAndAllOptions) : query.OrderBy(c => c.BaseAndAllOptions),
                "vendorname" => request.SortDescending ? query.OrderByDescending(c => c.VendorName) : query.OrderBy(c => c.VendorName),
                "agencyname" => request.SortDescending ? query.OrderByDescending(c => c.AgencyName) : query.OrderBy(c => c.AgencyName),
                "naicscode" => request.SortDescending ? query.OrderByDescending(c => c.NaicsCode) : query.OrderBy(c => c.NaicsCode),
                "setasidetype" => request.SortDescending ? query.OrderByDescending(c => c.SetAsideType) : query.OrderBy(c => c.SetAsideType),
                "typeofcontract" => request.SortDescending ? query.OrderByDescending(c => c.TypeOfContract) : query.OrderBy(c => c.TypeOfContract),
                _ => ordered
            };
        }

        // Join to reference tables for descriptions
        var enriched = from c in ordered
            join n in _context.RefNaicsCodes on c.NaicsCode equals n.NaicsCode into naicsJoin
            from n in naicsJoin.DefaultIfEmpty()
            join sa in _context.RefSetAsideTypes on c.SetAsideType equals sa.SetAsideCode into saJoin
            from sa in saJoin.DefaultIfEmpty()
            join psc in _context.RefPscCodeLatest on c.PscCode equals psc.PscCode into pscJoin
            from psc in pscJoin.DefaultIfEmpty()
            select new { Contract = c, NaicsDesc = n != null ? n.Description : null, SetAsideDesc = sa != null ? sa.Description : null, SetAsideCategory = sa != null ? sa.Category : null, PscDesc = psc != null ? psc.PscName : null };

        var results = await enriched
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .Select(x => new AwardSearchDto
            {
                ContractId = x.Contract.ContractId,
                SolicitationNumber = x.Contract.SolicitationNumber,
                AgencyName = x.Contract.AgencyName,
                ContractingOfficeName = x.Contract.ContractingOfficeName,
                VendorName = x.Contract.VendorName,
                VendorUei = x.Contract.VendorUei,
                DateSigned = x.Contract.DateSigned,
                EffectiveDate = x.Contract.EffectiveDate,
                CompletionDate = x.Contract.CompletionDate,
                DollarsObligated = x.Contract.DollarsObligated,
                BaseAndAllOptions = x.Contract.BaseAndAllOptions,
                NaicsCode = x.Contract.NaicsCode,
                NaicsDescription = x.NaicsDesc,
                PscCode = x.Contract.PscCode,
                PscDescription = x.PscDesc,
                SetAsideType = x.Contract.SetAsideType,
                SetAsideDescription = x.SetAsideDesc,
                SetAsideCategory = x.SetAsideCategory,
                TypeOfContract = x.Contract.TypeOfContract,
                NumberOfOffers = x.Contract.NumberOfOffers,
                ExtentCompeted = x.Contract.ExtentCompeted,
                Description = x.Contract.Description,
                DataSource = "fpds",
                FhOrgId = x.Contract.FhOrgId
            })
            .ToListAsync();

        // Fallback: if FPDS returned fewer results than page size, supplement with USASpending
        if (results.Count < request.PageSize)
        {
            var fpdsPoiids = results.Select(r => r.ContractId).ToHashSet();
            var usaResults = await SearchUsaspendingAsync(request, request.PageSize - results.Count, fpdsPoiids, vendorUeis);
            results.AddRange(usaResults);
            // Adjust total count
            totalCount += await CountUsaspendingAsync(request, fpdsPoiids, vendorUeis);
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

            // Look up reference descriptions for FPDS detail
            string? naicsDescription = null;
            string? pscDescription = null;
            string? setAsideDescription = null;
            string? setAsideCategory = null;

            if (!string.IsNullOrWhiteSpace(contract!.NaicsCode))
            {
                var naicsRef = await _context.RefNaicsCodes.AsNoTracking()
                    .FirstOrDefaultAsync(n => n.NaicsCode == contract.NaicsCode);
                naicsDescription = naicsRef?.Description;
            }

            if (!string.IsNullOrWhiteSpace(contract.PscCode))
            {
                var pscRef = await _context.RefPscCodes.AsNoTracking()
                    .Where(p => p.PscCode == contract.PscCode)
                    .OrderByDescending(p => p.StartDate)
                    .FirstOrDefaultAsync();
                pscDescription = pscRef?.PscName;
            }

            if (!string.IsNullOrWhiteSpace(contract.SetAsideType))
            {
                var saRef = await _context.RefSetAsideTypes.AsNoTracking()
                    .FirstOrDefaultAsync(sa => sa.SetAsideCode == contract.SetAsideType);
                setAsideDescription = saRef?.Description;
                setAsideCategory = saRef?.Category;
            }

            // Look up state/country names (COALESCE: fallback to raw code)
            string? fpdsPopStateName = contract.PopState;
            if (!string.IsNullOrWhiteSpace(contract.PopState))
            {
                var stateRef = await _context.RefStateCodes.AsNoTracking()
                    .FirstOrDefaultAsync(s => s.StateCode == contract.PopState && s.CountryCode == "USA");
                if (stateRef != null) fpdsPopStateName = stateRef.StateName;
            }

            string? fpdsPopCountryName = contract.PopCountry;
            if (!string.IsNullOrWhiteSpace(contract.PopCountry))
            {
                var countryRef = await _context.RefCountryCodes.AsNoTracking()
                    .FirstOrDefaultAsync(c => c.ThreeCode == contract.PopCountry);
                if (countryRef != null) fpdsPopCountryName = countryRef.CountryName;
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
                FundingSubtierCode = contract.FundingSubtierCode,
                FundingSubtierName = contract.FundingSubtierName,
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
                NaicsDescription = naicsDescription,
                PscCode = contract.PscCode,
                PscDescription = pscDescription,
                SetAsideType = contract.SetAsideType,
                SetAsideDescription = setAsideDescription,
                SetAsideCategory = setAsideCategory,
                TypeOfContract = contract.TypeOfContract,
                TypeOfContractPricing = contract.TypeOfContractPricing,
                Description = contract.Description,
                PopState = contract.PopState,
                PopStateName = fpdsPopStateName,
                PopCountry = contract.PopCountry,
                PopCountryName = fpdsPopCountryName,
                PopZip = contract.PopZip,
                ExtentCompeted = contract.ExtentCompeted,
                NumberOfOffers = contract.NumberOfOffers,
                SolicitationNumber = contract.SolicitationNumber,
                SolicitationDate = contract.SolicitationDate,
                SourceSelectionCode = contract.SourceSelectionCode,
                ContractBundlingCode = contract.ContractBundlingCode,
                AwardeeSocioeconomic = contract.AwardeeSocioeconomic,
                FhOrgId = contract.FhOrgId,
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

            // Look up reference descriptions for USASpending detail
            string? usaNaicsDesc = null;
            string? usaPscDesc = null;
            string? usaSaDesc = null;
            string? usaSaCat = null;

            if (!string.IsNullOrWhiteSpace(usaAward!.NaicsCode))
            {
                var naicsRef = await _context.RefNaicsCodes.AsNoTracking()
                    .FirstOrDefaultAsync(n => n.NaicsCode == usaAward.NaicsCode);
                usaNaicsDesc = naicsRef?.Description;
            }

            if (!string.IsNullOrWhiteSpace(usaAward.PscCode))
            {
                var pscRef = await _context.RefPscCodes.AsNoTracking()
                    .Where(p => p.PscCode == usaAward.PscCode)
                    .OrderByDescending(p => p.StartDate)
                    .FirstOrDefaultAsync();
                usaPscDesc = pscRef?.PscName;
            }

            if (!string.IsNullOrWhiteSpace(usaAward.TypeOfSetAside))
            {
                var saRef = await _context.RefSetAsideTypes.AsNoTracking()
                    .FirstOrDefaultAsync(sa => sa.SetAsideCode == usaAward.TypeOfSetAside);
                usaSaDesc = saRef?.Description;
                usaSaCat = saRef?.Category;
            }

            // Look up state/country names (COALESCE: fallback to raw code)
            string? usaPopStateName = usaAward.PopState;
            if (!string.IsNullOrWhiteSpace(usaAward.PopState))
            {
                var stateRef = await _context.RefStateCodes.AsNoTracking()
                    .FirstOrDefaultAsync(s => s.StateCode == usaAward.PopState && s.CountryCode == "USA");
                if (stateRef != null) usaPopStateName = stateRef.StateName;
            }

            string? usaPopCountryName = usaAward.PopCountry;
            if (!string.IsNullOrWhiteSpace(usaAward.PopCountry))
            {
                var countryRef = await _context.RefCountryCodes.AsNoTracking()
                    .FirstOrDefaultAsync(c => c.ThreeCode == usaAward.PopCountry);
                if (countryRef != null) usaPopCountryName = countryRef.CountryName;
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
                NaicsDescription = usaNaicsDesc,
                PscCode = usaAward.PscCode,
                PscDescription = usaPscDesc,
                SetAsideType = usaAward.TypeOfSetAside,
                SetAsideDescription = usaSaDesc,
                SetAsideCategory = usaSaCat,
                Description = usaAward.AwardDescription,
                PopState = usaAward.PopState,
                PopStateName = usaPopStateName,
                PopCountry = usaAward.PopCountry,
                PopCountryName = usaPopCountryName,
                PopZip = usaAward.PopZip,
                FhOrgId = usaAward.FhOrgId,
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

        var awardId = usaAward.GeneratedUniqueAwardId;
        var monthlyData = await _context.MonthlySpends.AsNoTracking()
            .Where(m => m.AwardId == awardId)
            .OrderBy(m => m.YearMonth)
            .Select(m => new MonthlySpendDto
            {
                YearMonth = m.YearMonth,
                Amount = m.Amount,
                TransactionCount = m.TransactionCount,
            })
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
        var results = await _context.VendorMarketShares.AsNoTracking()
            .Where(m => m.NaicsCode == naicsCode)
            .OrderByDescending(m => m.TotalValue)
            .Take(limit)
            .Select(m => new MarketShareDto
            {
                VendorName = m.VendorName,
                VendorUei = m.VendorUei,
                AwardCount = m.AwardCount,
                TotalValue = m.TotalValue ?? 0m,
                AverageValue = m.AverageValue ?? 0m,
                LastAwardDate = m.LastAwardDate,
            })
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
        AwardSearchRequest request, int limit, HashSet<string> excludePiids, HashSet<string>? vendorUeis = null)
    {
        var query = BuildUsaspendingQuery(request, excludePiids, vendorUeis);

        // Apply sort consistent with FPDS query
        IOrderedQueryable<UsaspendingAward> ordered = query.OrderByDescending(ua => ua.StartDate);

        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            ordered = request.SortBy.ToLowerInvariant() switch
            {
                "contractid" => request.SortDescending ? query.OrderByDescending(ua => ua.Piid) : query.OrderBy(ua => ua.Piid),
                "datesigned" => request.SortDescending ? query.OrderByDescending(ua => ua.StartDate) : query.OrderBy(ua => ua.StartDate),
                "baseandalloptions" or "baseandalloptionsvalue" or "value" => request.SortDescending ? query.OrderByDescending(ua => ua.BaseAndAllOptionsValue) : query.OrderBy(ua => ua.BaseAndAllOptionsValue),
                "vendorname" => request.SortDescending ? query.OrderByDescending(ua => ua.RecipientName) : query.OrderBy(ua => ua.RecipientName),
                "agencyname" => request.SortDescending ? query.OrderByDescending(ua => ua.AwardingAgencyName) : query.OrderBy(ua => ua.AwardingAgencyName),
                "naicscode" => request.SortDescending ? query.OrderByDescending(ua => ua.NaicsCode) : query.OrderBy(ua => ua.NaicsCode),
                "setasidetype" => request.SortDescending ? query.OrderByDescending(ua => ua.TypeOfSetAside) : query.OrderBy(ua => ua.TypeOfSetAside),
                _ => ordered
            };
        }

        // Join to reference tables for descriptions
        var usaEnriched = from ua in ordered
            join n in _context.RefNaicsCodes on ua.NaicsCode equals n.NaicsCode into naicsJoin
            from n in naicsJoin.DefaultIfEmpty()
            join sa in _context.RefSetAsideTypes on ua.TypeOfSetAside equals sa.SetAsideCode into saJoin
            from sa in saJoin.DefaultIfEmpty()
            join psc in _context.RefPscCodeLatest on ua.PscCode equals psc.PscCode into pscJoin
            from psc in pscJoin.DefaultIfEmpty()
            select new { Award = ua, NaicsDesc = n != null ? n.Description : null, SetAsideDesc = sa != null ? sa.Description : null, SetAsideCategory = sa != null ? sa.Category : null, PscDesc = psc != null ? psc.PscName : null };

        return await usaEnriched
            .Take(limit)
            .Select(x => new AwardSearchDto
            {
                ContractId = x.Award.Piid!,
                SolicitationNumber = x.Award.SolicitationIdentifier,
                AgencyName = x.Award.AwardingAgencyName,
                ContractingOfficeName = null,
                VendorName = x.Award.RecipientName,
                VendorUei = x.Award.RecipientUei,
                DateSigned = x.Award.StartDate,
                EffectiveDate = null,
                CompletionDate = null,
                DollarsObligated = x.Award.TotalObligation,
                BaseAndAllOptions = x.Award.BaseAndAllOptionsValue,
                NaicsCode = x.Award.NaicsCode,
                NaicsDescription = x.NaicsDesc,
                PscCode = x.Award.PscCode,
                PscDescription = x.PscDesc,
                SetAsideType = x.Award.TypeOfSetAside,
                SetAsideDescription = x.SetAsideDesc,
                SetAsideCategory = x.SetAsideCategory,
                TypeOfContract = null,
                NumberOfOffers = null,
                ExtentCompeted = null,
                Description = x.Award.AwardDescription,
                DataSource = "usaspending",
                FhOrgId = x.Award.FhOrgId
            })
            .ToListAsync();
    }

    private async Task<int> CountUsaspendingAsync(
        AwardSearchRequest request, HashSet<string> excludePiids, HashSet<string>? vendorUeis = null)
    {
        return await BuildUsaspendingQuery(request, excludePiids, vendorUeis).CountAsync();
    }

    private IQueryable<UsaspendingAward> BuildUsaspendingQuery(
        AwardSearchRequest request, HashSet<string> excludePiids, HashSet<string>? vendorUeis = null)
    {
        var query = _context.UsaspendingAwards.AsNoTracking()
            .Where(ua => ua.Piid != null);

        if (excludePiids.Count > 0)
            query = query.Where(ua => !excludePiids.Contains(ua.Piid!));

        if (!string.IsNullOrWhiteSpace(request.Piid))
            query = query.Where(ua => ua.Piid!.StartsWith(request.Piid));

        // Search both PIID and solicitation_identifier with prefix match.
        // Perf note: could switch to exact match (==) if this ever needs to be faster.
        if (!string.IsNullOrWhiteSpace(request.Solicitation))
            query = query.Where(ua => ua.Piid!.StartsWith(request.Solicitation)
                || (ua.SolicitationIdentifier != null && ua.SolicitationIdentifier.StartsWith(request.Solicitation)));

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(ua => ua.NaicsCode == request.Naics);

        if (!string.IsNullOrWhiteSpace(request.Agency))
        {
            var escapedAgency = EscapeLikePattern(request.Agency);
            query = query.Where(ua => ua.AwardingAgencyName != null && EF.Functions.Like(ua.AwardingAgencyName, $"%{escapedAgency}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.VendorUei))
            query = query.Where(ua => ua.RecipientUei == request.VendorUei);

        if (vendorUeis != null)
            query = query.Where(ua => ua.RecipientUei != null && vendorUeis.Contains(ua.RecipientUei));

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
    /// Resolves matching UEIs from the entity table for a vendor name search.
    /// Searches 870K entity rows instead of 28M award rows.
    /// </summary>
    private async Task<HashSet<string>> ResolveVendorUeisAsync(string vendorName)
    {
        var escaped = EscapeLikePattern(vendorName);
        var ueis = await _context.Entities.AsNoTracking()
            .TagWith("HINT:NO_INDEX(e idx_entity_name)")
            .Where(e => EF.Functions.Like(e.LegalBusinessName, $"%{escaped}%"))
            .Select(e => e.UeiSam)
            .ToListAsync();
        return ueis.ToHashSet();
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
