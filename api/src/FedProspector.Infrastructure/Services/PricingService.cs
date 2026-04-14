using FedProspector.Core.DTOs.Pricing;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using MySqlConnector;

namespace FedProspector.Infrastructure.Services;

public class PricingService : IPricingService
{
    /// <summary>
    /// Maps UI-friendly pricing type labels to FPDS type_of_contract_pricing codes.
    /// FPDS stores single-letter codes (J, T, K, etc.) and occasionally spelled-out
    /// values (FFP, TM, CPFF, etc.).  The UI sends "FFP", "T&amp;M", or "COST".
    /// </summary>
    private static readonly Dictionary<string, List<string>> PricingTypeCodes = new(StringComparer.OrdinalIgnoreCase)
    {
        ["FFP"]  = new() { "J", "FFP" },
        ["T&M"]  = new() { "T", "TM" },
        ["COST"] = new() { "K", "L", "R", "S", "U", "V", "Y", "CPFF", "CPAF", "CPIF" },
    };

    private readonly FedProspectorDbContext _context;
    private readonly ILogger<PricingService> _logger;

    public PricingService(FedProspectorDbContext context, ILogger<PricingService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<List<CanonicalCategoryDto>> GetCanonicalCategoriesAsync(string? group = null)
    {
        var query = _context.CanonicalLaborCategories.AsNoTracking().AsQueryable();

        if (!string.IsNullOrWhiteSpace(group))
            query = query.Where(c => c.CategoryGroup == group);

        return await query
            .OrderBy(c => c.CategoryGroup)
            .ThenBy(c => c.Name)
            .Select(c => new CanonicalCategoryDto
            {
                Id = c.Id,
                Name = c.Name,
                Group = c.CategoryGroup,
                OnetCode = c.OnetCode,
                Description = c.Description
            })
            .ToListAsync();
    }

    public async Task<List<CanonicalCategoryDto>> SearchLaborCategoriesAsync(string query)
    {
        if (string.IsNullOrWhiteSpace(query))
            return new List<CanonicalCategoryDto>();

        var searchTerm = EscapeLikeWildcards(query.Trim());

        // Search canonical categories by name match
        var results = await _context.CanonicalLaborCategories
            .AsNoTracking()
            .Where(c => EF.Functions.Like(c.Name, $"%{searchTerm}%")
                        || (c.Description != null && EF.Functions.Like(c.Description, $"%{searchTerm}%")))
            .OrderBy(c => c.Name)
            .Take(50)
            .Select(c => new CanonicalCategoryDto
            {
                Id = c.Id,
                Name = c.Name,
                Group = c.CategoryGroup,
                OnetCode = c.OnetCode,
                Description = c.Description
            })
            .ToListAsync();

        return results;
    }

    public async Task<List<RateHeatmapCell>> GetRateHeatmapAsync(RateHeatmapRequest request)
    {
        var query = _context.LaborRateSummaries.AsNoTracking().AsQueryable();

        if (!string.IsNullOrWhiteSpace(request.CategoryGroup))
            query = query.Where(s => s.CategoryGroup == request.CategoryGroup);

        if (!string.IsNullOrWhiteSpace(request.Worksite))
            query = query.Where(s => s.Worksite == request.Worksite);

        if (!string.IsNullOrWhiteSpace(request.EducationLevel))
            query = query.Where(s => s.EducationLevel == request.EducationLevel);

        // Join to canonical to get the name
        var cells = await query
            .Join(_context.CanonicalLaborCategories.AsNoTracking(),
                s => s.CanonicalId,
                c => c.Id,
                (s, c) => new RateHeatmapCell
                {
                    CanonicalName = c.Name,
                    CategoryGroup = s.CategoryGroup,
                    Worksite = s.Worksite,
                    EducationLevel = s.EducationLevel,
                    RateCount = s.RateCount,
                    MinRate = s.MinRate ?? 0m,
                    AvgRate = s.AvgRate ?? 0m,
                    MaxRate = s.MaxRate ?? 0m,
                    P25Rate = s.P25Rate ?? 0m,
                    MedianRate = s.MedianRate ?? 0m,
                    P75Rate = s.P75Rate ?? 0m
                })
            .OrderBy(c => c.CategoryGroup)
            .ThenBy(c => c.CanonicalName)
            .ToListAsync();

        return cells;
    }

    public async Task<RateDistributionDto> GetRateDistributionAsync(int canonicalId)
    {
        var canonical = await _context.CanonicalLaborCategories
            .AsNoTracking()
            .FirstOrDefaultAsync(c => c.Id == canonicalId);

        if (canonical == null)
        {
            return new RateDistributionDto { CanonicalId = canonicalId };
        }

        // Get all rates for this canonical category via labor_category_mapping -> gsa_labor_rate
        var rates = await _context.LaborCategoryMappings
            .AsNoTracking()
            .Where(m => m.CanonicalId == canonicalId && m.Source == "GSA_CALC")
            .Join(_context.GsaLaborRates.AsNoTracking(),
                m => m.RawLaborCategory,
                g => g.LaborCategory,
                (m, g) => g.CurrentPrice)
            .Where(price => price != null && price > 0)
            .Select(price => price!.Value)
            .OrderBy(p => p)
            .ToListAsync();

        if (rates.Count == 0)
        {
            return new RateDistributionDto
            {
                CanonicalId = canonicalId,
                CanonicalName = canonical.Name
            };
        }

        return new RateDistributionDto
        {
            CanonicalId = canonicalId,
            CanonicalName = canonical.Name,
            Rates = rates,
            Count = rates.Count,
            MinRate = rates[0],
            MaxRate = rates[^1],
            AvgRate = Math.Round(rates.Average(), 2),
            P25Rate = Percentile(rates, 25),
            MedianRate = Percentile(rates, 50),
            P75Rate = Percentile(rates, 75)
        };
    }

    public async Task<PriceToWinResponse> EstimatePriceToWinAsync(PriceToWinRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.NaicsCode))
        {
            return new PriceToWinResponse();
        }

        var fiveYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-5));

        var escapedAgency = !string.IsNullOrWhiteSpace(request.AgencyName)
            ? EscapeLikeWildcards(request.AgencyName)
            : null;

        // When FPDS-only filters are requested, pre-fetch matching PIIDs from fpds_contract
        var hasFpdsFilters = !string.IsNullOrWhiteSpace(request.SourceSelectionCode)
                             || !string.IsNullOrWhiteSpace(request.ContractPricingType);
        HashSet<string>? fpdsMatchingPiids = null;
        bool filterFallback = false;

        if (hasFpdsFilters)
        {
            var fpdsFilterQuery = _context.FpdsContracts.AsNoTracking()
                .Where(c => c.NaicsCode == request.NaicsCode
                            && c.ModificationNumber == "0"
                            && c.DateSigned != null
                            && c.DateSigned >= fiveYearsAgo);

            if (!string.IsNullOrWhiteSpace(request.SourceSelectionCode))
                fpdsFilterQuery = fpdsFilterQuery.Where(c => c.SourceSelectionCode == request.SourceSelectionCode);

            if (!string.IsNullOrWhiteSpace(request.ContractPricingType)
                && PricingTypeCodes.TryGetValue(request.ContractPricingType, out var codes))
                fpdsFilterQuery = fpdsFilterQuery.Where(c => c.TypeOfContractPricing != null
                                                             && codes.Contains(c.TypeOfContractPricing));

            var matchedIds = await fpdsFilterQuery
                .Select(c => c.ContractId)
                .Distinct()
                .ToListAsync();

            fpdsMatchingPiids = new HashSet<string>(matchedIds, StringComparer.OrdinalIgnoreCase);
        }

        // Primary award value analysis uses usaspending_award (28.7M rows, authoritative source)
        var query = _context.UsaspendingAwards.AsNoTracking()
            .Where(a => a.NaicsCode == request.NaicsCode
                        && a.StartDate != null
                        && a.StartDate >= fiveYearsAgo
                        && a.BaseAndAllOptionsValue != null
                        && a.BaseAndAllOptionsValue > 0);

        if (escapedAgency != null)
            query = query.Where(a => a.AwardingAgencyName != null && EF.Functions.Like(a.AwardingAgencyName, $"%{escapedAgency}%"));

        if (!string.IsNullOrWhiteSpace(request.SetAsideType))
            query = query.Where(a => a.TypeOfSetAside == request.SetAsideType);

        // ContractType filter not available in USASpending entity — skip silently

        var awards = await query
            .OrderByDescending(a => a.StartDate)
            .Take(500)
            .Select(a => new
            {
                ContractId = a.Piid ?? a.GeneratedUniqueAwardId,
                a.RecipientName,
                a.BaseAndAllOptionsValue,
                a.AwardingAgencyName,
                a.StartDate,
                a.EndDate
            })
            .ToListAsync();

        if (awards.Count == 0)
        {
            return new PriceToWinResponse { Confidence = 0 };
        }

        // Apply FPDS cross-filter on PIID if source selection / contract pricing filters are active
        var filteredAwards = awards;
        if (fpdsMatchingPiids != null)
        {
            var fpdsFiltered = awards
                .Where(a => a.ContractId != null && fpdsMatchingPiids.Contains(a.ContractId))
                .ToList();

            if (fpdsFiltered.Count >= 5)
            {
                filteredAwards = fpdsFiltered;
            }
            else
            {
                // Below useful threshold — fall back to unfiltered and note it
                filterFallback = true;
                _logger.LogInformation(
                    "FPDS filter reduced comparable set to {Count} (below threshold of 5), falling back to unfiltered",
                    fpdsFiltered.Count);
            }
        }

        var values = filteredAwards
            .Select(a => a.BaseAndAllOptionsValue!.Value)
            .OrderBy(v => v)
            .ToList();

        var p25 = Percentile(values, 25);
        var p50 = Percentile(values, 50);
        var p75 = Percentile(values, 75);

        // Adjust target percentile based on source selection regime
        // LPTA rewards lowest price → target P25; Best Value weighs technical factors → P50
        decimal targetEstimate = p50;
        string? sourceSelectionRegime = null;

        if (!filterFallback && !string.IsNullOrWhiteSpace(request.SourceSelectionCode))
        {
            sourceSelectionRegime = request.SourceSelectionCode;
            targetEstimate = request.SourceSelectionCode.ToUpperInvariant() switch
            {
                "LPTA" => p25,
                _ => p50  // Best Value and other regimes use median
            };
        }

        // Competition stats from FPDS supplement (NumberOfOffers is FPDS-only)
        var competitionStats = await GetCompetitionStatsFromFpdsAsync(
            request.NaicsCode, fiveYearsAgo, escapedAgency, values, p50);

        // Top 20 comparable awards
        var comparableAwards = filteredAwards.Take(20).Select(a =>
        {
            int? popMonths = null;
            if (a.StartDate.HasValue && a.EndDate.HasValue)
            {
                popMonths = (int)Math.Ceiling(
                    (a.EndDate.Value.ToDateTime(TimeOnly.MinValue) - a.StartDate.Value.ToDateTime(TimeOnly.MinValue)).TotalDays / 30.0);
            }

            return new ComparableAwardDto
            {
                ContractId = a.ContractId,
                Vendor = a.RecipientName,
                AwardValue = a.BaseAndAllOptionsValue,
                Offers = null, // NumberOfOffers not available in USASpending
                Agency = a.AwardingAgencyName,
                AwardDate = a.StartDate,
                PopMonths = popMonths
            };
        }).ToList();

        // Confidence based on sample size
        var confidence = filteredAwards.Count switch
        {
            >= 100 => 0.9m,
            >= 50 => 0.8m,
            >= 20 => 0.7m,
            >= 10 => 0.5m,
            >= 5 => 0.3m,
            _ => 0.1m
        };

        return new PriceToWinResponse
        {
            LowEstimate = p25,
            TargetEstimate = targetEstimate,
            HighEstimate = p75,
            Confidence = confidence,
            ComparableCount = filteredAwards.Count,
            SourceSelectionRegime = sourceSelectionRegime,
            FilterFallback = filterFallback,
            ComparableAwards = comparableAwards,
            CompetitionStats = competitionStats
        };
    }

    public async Task<List<SubBenchmarkDto>> GetSubBenchmarksAsync(SubBenchmarkRequest request)
    {
        var query = _context.SamSubawards.AsNoTracking()
            .Where(s => s.SubAmount != null && s.SubAmount > 0);

        if (!string.IsNullOrWhiteSpace(request.NaicsCode))
            query = query.Where(s => s.NaicsCode == request.NaicsCode);

        if (!string.IsNullOrWhiteSpace(request.AgencyName))
        {
            var escapedAgency = EscapeLikeWildcards(request.AgencyName);
            query = query.Where(s => s.PrimeAgencyName != null && EF.Functions.Like(s.PrimeAgencyName, $"%{escapedAgency}%"));
        }

        var benchmarks = await query
            .GroupBy(s => new { s.NaicsCode, s.PrimeAgencyName, s.SubBusinessType })
            .Select(g => new SubBenchmarkDto
            {
                NaicsCode = g.Key.NaicsCode,
                AgencyName = g.Key.PrimeAgencyName,
                SubBusinessType = g.Key.SubBusinessType,
                SubCount = g.Count(),
                TotalValue = g.Sum(s => s.SubAmount ?? 0m),
                AvgValue = g.Average(s => s.SubAmount ?? 0m),
                MinValue = g.Min(s => s.SubAmount ?? 0m),
                MaxValue = g.Max(s => s.SubAmount ?? 0m)
            })
            .Where(b => b.SubCount >= 3)
            .OrderByDescending(b => b.TotalValue)
            .Take(100)
            .ToListAsync();

        // Round decimal values
        foreach (var b in benchmarks)
        {
            b.AvgValue = Math.Round(b.AvgValue, 2);
            b.TotalValue = Math.Round(b.TotalValue, 2);
        }

        return benchmarks;
    }

    public async Task<List<SubRatioDto>> GetSubRatiosAsync(string? naicsCode)
    {
        // Calculate sub/prime ratios by NAICS
        // Join subawards to usaspending_award on prime PIID to get prime value, then compute ratio
        var query = _context.SamSubawards.AsNoTracking()
            .Where(s => s.SubAmount != null && s.SubAmount > 0 && s.PrimePiid != null);

        if (!string.IsNullOrWhiteSpace(naicsCode))
            query = query.Where(s => s.NaicsCode == naicsCode);

        // Join to usaspending_award to get prime contract value (authoritative source)
        var joined = query
            .Join(
                _context.UsaspendingAwards.AsNoTracking()
                    .Where(a => a.BaseAndAllOptionsValue != null
                                && a.BaseAndAllOptionsValue > 0
                                && a.Piid != null),
                s => s.PrimePiid,
                a => a.Piid,
                (s, a) => new
                {
                    s.NaicsCode,
                    SubAmount = s.SubAmount!.Value,
                    PrimeValue = a.BaseAndAllOptionsValue!.Value
                })
            .Where(x => x.PrimeValue > 0);

        var ratios = await joined
            .GroupBy(x => x.NaicsCode)
            .Select(g => new
            {
                NaicsCode = g.Key,
                Count = g.Count(),
                Ratios = g.Select(x => x.SubAmount / x.PrimeValue).ToList()
            })
            .Where(g => g.Count >= 3)
            .Take(50)
            .ToListAsync();

        var results = ratios.Select(g =>
        {
            var sorted = g.Ratios.OrderBy(v => v).ToList();
            return new SubRatioDto
            {
                NaicsCode = g.NaicsCode,
                AvgSubRatio = Math.Round(sorted.Average(), 4),
                MedianSubRatio = Percentile(sorted, 50),
                Count = g.Count
            };
        }).ToList();

        return results;
    }

    public async Task<List<RateTrendDto>> GetRateTrendsAsync(RateTrendRequest request)
    {
        var cutoffYear = DateTime.UtcNow.Year - request.Years;

        // Get rates for this canonical category by year via mapping
        var mappedCategories = await _context.LaborCategoryMappings
            .AsNoTracking()
            .Where(m => m.CanonicalId == request.CanonicalId && m.Source == "GSA_CALC")
            .Select(m => m.RawLaborCategory)
            .ToListAsync();

        if (mappedCategories.Count == 0)
            return new List<RateTrendDto>();

        var ratesByYear = await _context.GsaLaborRates
            .AsNoTracking()
            .Where(g => mappedCategories.Contains(g.LaborCategory)
                        && g.CurrentPrice != null
                        && g.CurrentPrice > 0
                        && g.ContractStart != null
                        && g.ContractStart.Value.Year >= cutoffYear)
            .GroupBy(g => g.ContractStart!.Value.Year)
            .Select(g => new
            {
                Year = g.Key,
                AvgRate = g.Average(r => r.CurrentPrice!.Value),
                MinRate = g.Min(r => r.CurrentPrice!.Value),
                MaxRate = g.Max(r => r.CurrentPrice!.Value),
                RateCount = g.Count()
            })
            .OrderBy(g => g.Year)
            .ToListAsync();

        // Compute YoY change
        var trends = new List<RateTrendDto>();
        for (int i = 0; i < ratesByYear.Count; i++)
        {
            var r = ratesByYear[i];
            decimal? yoy = null;
            if (i > 0 && ratesByYear[i - 1].AvgRate > 0)
            {
                yoy = Math.Round((r.AvgRate - ratesByYear[i - 1].AvgRate) / ratesByYear[i - 1].AvgRate * 100, 2);
            }

            trends.Add(new RateTrendDto
            {
                Year = r.Year,
                AvgRate = Math.Round(r.AvgRate, 2),
                MinRate = Math.Round(r.MinRate, 2),
                MaxRate = Math.Round(r.MaxRate, 2),
                RateCount = r.RateCount,
                YoyChangePct = yoy
            });
        }

        return trends;
    }

    public async Task<List<EscalationForecastDto>> GetEscalationForecastAsync(int canonicalId, int years = 5)
    {
        // Get historical trends
        var trends = await GetRateTrendsAsync(new RateTrendRequest { CanonicalId = canonicalId, Years = 10 });

        if (trends.Count < 2)
        {
            return new List<EscalationForecastDto>
            {
                new EscalationForecastDto
                {
                    Year = DateTime.UtcNow.Year + 1,
                    ProjectedRate = 0,
                    ConfidenceLow = 0,
                    ConfidenceHigh = 0,
                    Method = "Insufficient data"
                }
            };
        }

        // Linear regression on historical avg rates
        var xs = trends.Select((t, i) => (double)i).ToArray();
        var ys = trends.Select(t => (double)t.AvgRate).ToArray();

        var n = xs.Length;
        var sumX = xs.Sum();
        var sumY = ys.Sum();
        var sumXY = xs.Zip(ys, (x, y) => x * y).Sum();
        var sumX2 = xs.Sum(x => x * x);

        var denominator = n * sumX2 - sumX * sumX;

        double slope;
        double intercept;

        // FIX 6: Guard against division by zero (all same year / single x value)
        if (Math.Abs(denominator) < 1e-10)
        {
            // Flat projection using last known rate
            slope = 0;
            intercept = ys[^1];
        }
        else
        {
            slope = (n * sumXY - sumX * sumY) / denominator;
            intercept = (sumY - slope * sumX) / n;
        }

        // Compute standard error for confidence band
        var residuals = xs.Zip(ys, (x, y) => y - (intercept + slope * x)).ToArray();
        var sse = residuals.Sum(r => r * r);
        var se = Math.Sqrt(sse / Math.Max(n - 2, 1));

        var baseYear = trends[^1].Year;

        // Preload BLS ECI data for the range of years
        var forecastYears = Enumerable.Range(baseYear + 1, years).ToList();
        var blsLookupYears = forecastYears.Select(y => y - 1).ToList();
        var blsData = await _context.BlsCostIndices
            .AsNoTracking()
            .Where(b => blsLookupYears.Contains(b.Year))
            .GroupBy(b => b.Year)
            .Select(g => new { Year = g.Key, Value = g.OrderByDescending(b => b.Period).First().Value })
            .ToDictionaryAsync(b => b.Year, b => b.Value);

        // Generate projections for each year
        var forecasts = new List<EscalationForecastDto>();
        for (int i = 0; i < years; i++)
        {
            var projectedYear = baseYear + 1 + i;
            var nextIndex = (double)(n + i);
            var projected = intercept + slope * nextIndex;

            // Widen confidence band further out
            var bandMultiplier = 1.96 * (1.0 + i * 0.1);

            decimal? blsIndex = null;
            if (blsData.TryGetValue(projectedYear - 1, out var val))
                blsIndex = val;

            forecasts.Add(new EscalationForecastDto
            {
                Year = projectedYear,
                ProjectedRate = Math.Round((decimal)projected, 2),
                ConfidenceLow = Math.Round((decimal)(projected - bandMultiplier * se), 2),
                ConfidenceHigh = Math.Round((decimal)(projected + bandMultiplier * se), 2),
                BlsEciIndex = blsIndex,
                Method = Math.Abs(denominator) < 1e-10 ? "Flat projection (single data point)" : "Linear regression"
            });
        }

        return forecasts;
    }

    public async Task<IgceResponse> EstimateIgceAsync(IgceRequest request)
    {
        _logger.LogInformation("IGCE request: NoticeId={NoticeId}, NaicsCode={NaicsCode}, Agency={Agency}",
            request.NoticeId, request.NaicsCode, request.AgencyName);

        // Auto-populate from opportunity if NoticeId provided but NAICS/Agency missing
        if (!string.IsNullOrWhiteSpace(request.NoticeId)
            && string.IsNullOrWhiteSpace(request.NaicsCode))
        {
            // Support both notice_id and solicitation_number lookups
            var opp = await _context.Opportunities.AsNoTracking()
                .FirstOrDefaultAsync(o => o.NoticeId == request.NoticeId
                    || o.SolicitationNumber == request.NoticeId);

            _logger.LogInformation("IGCE opportunity lookup: found={Found}, NAICS={Naics}, Agency={Agency}",
                opp != null, opp?.NaicsCode, opp?.DepartmentName);

            if (opp != null)
            {
                request.NaicsCode ??= opp.NaicsCode;
                request.AgencyName ??= opp.DepartmentName;
                // Use internal notice_id for burn rate lookup
                request.NoticeId = opp.NoticeId;
            }
        }

        _logger.LogInformation("IGCE after lookup: NaicsCode={NaicsCode}, Agency={Agency}",
            request.NaicsCode, request.AgencyName);

        var methods = new List<IgceMethodResult>();

        // Method 1: Historical analog -- average of comparable past awards
        var analogEstimate = await EstimateByHistoricalAnalogAsync(request);
        _logger.LogInformation("IGCE method 1 (historical analog): {Result}",
            analogEstimate != null ? $"${analogEstimate.Estimate}" : "null");
        if (analogEstimate != null)
            methods.Add(analogEstimate);

        // Method 2: Labor bottoms-up -- labor categories x median GSA rates x hours
        var laborEstimate = await EstimateByLaborBottomsUpAsync(request);
        _logger.LogInformation("IGCE method 2 (labor bottoms-up): {Result}",
            laborEstimate != null ? $"${laborEstimate.Estimate}" : "null");
        if (laborEstimate != null)
            methods.Add(laborEstimate);

        // Method 3: Burn rate extrapolation -- incumbent monthly burn rate x new POP
        var burnRateEstimate = await EstimateByBurnRateAsync(request);
        _logger.LogInformation("IGCE method 3 (burn rate): {Result}",
            burnRateEstimate != null ? $"${burnRateEstimate.Estimate}" : "null");
        if (burnRateEstimate != null)
            methods.Add(burnRateEstimate);

        if (methods.Count == 0)
        {
            _logger.LogWarning("IGCE: all methods returned null for NAICS={NaicsCode}", request.NaicsCode);
            return new IgceResponse { ConfidenceLevel = "None" };
        }

        // Method 4: Weighted ensemble
        var totalConfidence = methods.Sum(m => m.Confidence);
        var weightedEstimate = totalConfidence > 0
            ? methods.Sum(m => m.Estimate * m.Confidence) / totalConfidence
            : methods.Average(m => m.Estimate);

        methods.Add(new IgceMethodResult
        {
            MethodName = "Weighted Ensemble",
            Estimate = Math.Round(weightedEstimate, 2),
            Confidence = Math.Round(Math.Min(totalConfidence / methods.Count, 1.0m), 2),
            Explanation = $"Weighted average of {methods.Count - 1} methods by confidence score",
            DataPoints = methods.Sum(m => m.DataPoints)
        });

        var avgConfidence = methods.Count > 1 ? totalConfidence / (methods.Count - 1) : totalConfidence;
        var confidenceLevel = avgConfidence switch
        {
            >= 0.7m => "High",
            >= 0.4m => "Medium",
            _ => "Low"
        };

        return new IgceResponse
        {
            Methods = methods,
            WeightedEstimate = Math.Round(weightedEstimate, 2),
            ConfidenceLevel = confidenceLevel
        };
    }

    public async Task<RateRangeResponse> GetRateRangeAsync(RateRangeRequest request)
    {
        var canonical = await _context.CanonicalLaborCategories
            .AsNoTracking()
            .FirstOrDefaultAsync(c => c.Id == request.CanonicalId);

        if (canonical == null)
            return new RateRangeResponse { CanonicalId = request.CanonicalId };

        var response = new RateRangeResponse
        {
            CanonicalId = request.CanonicalId,
            CanonicalName = canonical.Name
        };

        // SCA floor: sca_wage_rate -> sca_wage_determination (is_current=1) -> labor_category_mapping (source='SCA')
        var scaSql = @"
            SELECT wr.hourly_rate, wr.fringe_rate, wd.area_name, wd.wd_number, wd.effective_date
            FROM sca_wage_rate wr
            JOIN sca_wage_determination wd ON wd.id = wr.wd_id
            JOIN labor_category_mapping lcm ON lcm.raw_labor_category = wr.occupation_title
                AND lcm.source = 'SCA'
            WHERE wd.is_current = 1
              AND lcm.canonical_id = @canonicalId";

        var scaParams = new List<MySqlParameter>
        {
            new("@canonicalId", request.CanonicalId)
        };

        if (!string.IsNullOrWhiteSpace(request.State))
        {
            scaSql += " AND wd.state_code = @state";
            scaParams.Add(new MySqlParameter("@state", request.State));
        }

        if (!string.IsNullOrWhiteSpace(request.County))
        {
            scaSql += " AND wd.county_name = @county";
            scaParams.Add(new MySqlParameter("@county", request.County));
        }

        scaSql += " ORDER BY wr.hourly_rate ASC LIMIT 1";

        var connection = _context.Database.GetDbConnection();
        try
        {
            await _context.Database.OpenConnectionAsync();

            using (var cmd = connection.CreateCommand())
            {
                cmd.CommandText = scaSql;
                foreach (var p in scaParams)
                    cmd.Parameters.Add(p);

                using var reader = await cmd.ExecuteReaderAsync();
                if (await reader.ReadAsync())
                {
                    response.ScaFloorRate = reader.IsDBNull(0) ? null : reader.GetDecimal(0);
                    response.ScaFringe = reader.IsDBNull(1) ? null : reader.GetDecimal(1);
                    response.Area = reader.IsDBNull(2) ? null : reader.GetString(2);
                    response.WdNumber = reader.IsDBNull(3) ? null : reader.GetString(3);
                    response.WdEffectiveDate = reader.IsDBNull(4) ? null : reader.GetDateTime(4);

                    if (response.ScaFloorRate.HasValue && response.ScaFringe.HasValue)
                        response.ScaFullCost = response.ScaFloorRate.Value + response.ScaFringe.Value;
                }
            }
        }
        finally
        {
            await _context.Database.CloseConnectionAsync();
        }

        // GSA ceiling from labor_rate_summary
        var summary = await _context.LaborRateSummaries
            .AsNoTracking()
            .Where(s => s.CanonicalId == request.CanonicalId)
            .FirstOrDefaultAsync();

        if (summary != null)
        {
            response.GsaCeilingRate = summary.MedianRate;
            response.GsaP25Rate = summary.P25Rate;
            response.GsaP75Rate = summary.P75Rate;
            response.GsaRateCount = summary.RateCount;
        }

        // Compute spread
        if (response.GsaCeilingRate.HasValue && response.ScaFullCost.HasValue && response.ScaFullCost > 0)
        {
            response.Spread = Math.Round(response.GsaCeilingRate.Value - response.ScaFullCost.Value, 2);
            response.SpreadPct = Math.Round(
                (response.GsaCeilingRate.Value - response.ScaFullCost.Value) / response.ScaFullCost.Value * 100, 2);
        }

        return response;
    }

    public async Task<ScaComplianceResponse> CheckScaComplianceAsync(ScaComplianceRequest request)
    {
        var response = new ScaComplianceResponse();

        // Batch-load canonical names
        var canonicalIds = request.LineItems.Select(li => li.CanonicalId).Distinct().ToList();
        var canonicals = await _context.CanonicalLaborCategories
            .AsNoTracking()
            .Where(c => canonicalIds.Contains(c.Id))
            .ToDictionaryAsync(c => c.Id, c => c.Name);

        // Batch-load SCA rates for all requested canonical IDs + location
        var scaSql = @"
            SELECT lcm.canonical_id, wr.hourly_rate, wr.fringe_rate, wd.wd_number
            FROM sca_wage_rate wr
            JOIN sca_wage_determination wd ON wd.id = wr.wd_id
            JOIN labor_category_mapping lcm ON lcm.raw_labor_category = wr.occupation_title
                AND lcm.source = 'SCA'
            WHERE wd.is_current = 1
              AND lcm.canonical_id IN ({0})";

        var paramPlaceholders = new List<string>();
        var scaParams = new List<MySqlParameter>();
        for (int i = 0; i < canonicalIds.Count; i++)
        {
            paramPlaceholders.Add($"@cid{i}");
            scaParams.Add(new MySqlParameter($"@cid{i}", canonicalIds[i]));
        }

        scaSql = string.Format(scaSql, string.Join(",", paramPlaceholders));

        if (!string.IsNullOrWhiteSpace(request.State))
        {
            scaSql += " AND wd.state_code = @state";
            scaParams.Add(new MySqlParameter("@state", request.State));
        }

        if (!string.IsNullOrWhiteSpace(request.County))
        {
            scaSql += " AND wd.county_name = @county";
            scaParams.Add(new MySqlParameter("@county", request.County));
        }

        // For each canonical_id, take the row with the lowest hourly_rate (most conservative floor)
        var scaRates = new Dictionary<int, (decimal HourlyRate, decimal? Fringe, string? WdNumber)>();

        var connection = _context.Database.GetDbConnection();
        try
        {
            await _context.Database.OpenConnectionAsync();

            using var cmd = connection.CreateCommand();
            cmd.CommandText = scaSql;
            foreach (var p in scaParams)
                cmd.Parameters.Add(p);

            using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                var cid = reader.GetInt32(0);
                var hourly = reader.IsDBNull(1) ? (decimal?)null : reader.GetDecimal(1);
                var fringe = reader.IsDBNull(2) ? (decimal?)null : reader.GetDecimal(2);
                var wdNum = reader.IsDBNull(3) ? null : reader.GetString(3);

                if (hourly.HasValue && (!scaRates.ContainsKey(cid) || hourly.Value < scaRates[cid].HourlyRate))
                {
                    scaRates[cid] = (hourly.Value, fringe, wdNum);
                }
            }
        }
        finally
        {
            await _context.Database.CloseConnectionAsync();
        }

        foreach (var item in request.LineItems)
        {
            var result = new ScaComplianceResult
            {
                CanonicalId = item.CanonicalId,
                CanonicalName = canonicals.GetValueOrDefault(item.CanonicalId, ""),
                ProposedRate = item.ProposedRate
            };

            if (!scaRates.TryGetValue(item.CanonicalId, out var sca))
            {
                result.Status = "Unmapped";
                response.UnmappedCount++;
                response.Results.Add(result);
                continue;
            }

            result.ScaMinimumRate = sca.HourlyRate;
            result.ScaFringe = sca.Fringe;
            result.ScaFullCost = sca.HourlyRate + (sca.Fringe ?? 0m);
            result.WdNumber = sca.WdNumber;

            // Compare: if proposed rate includes fringe, compare to full cost; otherwise compare to hourly only
            var scaThreshold = item.IncludesFringe ? result.ScaFullCost.Value : sca.HourlyRate;

            if (item.ProposedRate >= scaThreshold)
            {
                result.Status = "Compliant";
                response.CompliantCount++;
            }
            else
            {
                result.Status = "Violation";
                result.Shortfall = Math.Round(scaThreshold - item.ProposedRate, 2);
                response.ViolationCount++;
            }

            if (sca.Fringe.HasValue)
                response.TotalFringeObligation += sca.Fringe.Value;

            response.Results.Add(result);
        }

        response.AllCompliant = response.ViolationCount == 0 && response.UnmappedCount == 0;
        response.TotalFringeObligation = Math.Round(response.TotalFringeObligation, 2);

        return response;
    }

    public async Task<List<ScaAreaRateDto>> GetScaAreaRatesAsync(ScaAreaRateRequest request)
    {
        var sb = new System.Text.StringBuilder();
        sb.Append(@"
            SELECT wd.state_code, wd.county_name, wd.area_name,
                   wr.occupation_code, wr.occupation_title,
                   wr.hourly_rate, wr.fringe_rate, wd.wd_number, wd.revision, wd.effective_date
            FROM sca_wage_rate wr
            JOIN sca_wage_determination wd ON wd.id = wr.wd_id
            WHERE wd.is_current = 1");

        var parameters = new List<MySqlParameter>();

        if (!string.IsNullOrWhiteSpace(request.OccupationTitle))
        {
            sb.Append(" AND wr.occupation_title LIKE @occupationTitle");
            parameters.Add(new MySqlParameter("@occupationTitle", $"%{request.OccupationTitle.Trim()}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.State))
        {
            sb.Append(" AND wd.state_code = @state");
            parameters.Add(new MySqlParameter("@state", request.State.Trim().ToUpper()));
        }

        if (!string.IsNullOrWhiteSpace(request.County))
        {
            sb.Append(" AND wd.county_name LIKE @county");
            parameters.Add(new MySqlParameter("@county", $"%{request.County.Trim()}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.WdNumber))
        {
            sb.Append(" AND wd.wd_number LIKE @wdNumber");
            parameters.Add(new MySqlParameter("@wdNumber", $"%{request.WdNumber.Trim()}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.AreaName))
        {
            sb.Append(" AND wd.area_name LIKE @areaName");
            parameters.Add(new MySqlParameter("@areaName", $"%{request.AreaName.Trim()}%"));
        }

        sb.Append(@"
            ORDER BY wd.state_code, wd.county_name, wr.occupation_code
            LIMIT 2000");

        var results = new List<ScaAreaRateDto>();
        var connection = _context.Database.GetDbConnection();
        try
        {
            await _context.Database.OpenConnectionAsync();

            using var cmd = connection.CreateCommand();
            cmd.CommandText = sb.ToString();
            foreach (var p in parameters)
                cmd.Parameters.Add(p);

            using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                var hourly = reader.IsDBNull(5) ? 0m : reader.GetDecimal(5);
                var fringe = reader.IsDBNull(6) ? 0m : reader.GetDecimal(6);

                results.Add(new ScaAreaRateDto
                {
                    State = reader.IsDBNull(0) ? "" : reader.GetString(0),
                    County = reader.IsDBNull(1) ? null : reader.GetString(1),
                    AreaName = reader.IsDBNull(2) ? "" : reader.GetString(2),
                    OccupationCode = reader.IsDBNull(3) ? "" : reader.GetString(3),
                    OccupationTitle = reader.IsDBNull(4) ? "" : reader.GetString(4),
                    HourlyRate = hourly,
                    Fringe = fringe,
                    FullCost = hourly + fringe,
                    WdNumber = reader.IsDBNull(7) ? null : reader.GetString(7),
                    Revision = reader.IsDBNull(8) ? null : reader.GetInt32(8),
                    EffectiveDate = reader.IsDBNull(9) ? null : reader.GetDateTime(9)
                });
            }
        }
        finally
        {
            await _context.Database.CloseConnectionAsync();
        }

        return results;
    }

    public async Task<List<string>> GetScaOccupationsAsync()
    {
        var sql = @"
            SELECT DISTINCT TRIM(SUBSTRING_INDEX(occupation_title, '(see', 1)) AS title
            FROM sca_wage_rate
            ORDER BY title";

        var rawTitles = new List<string>();
        var connection = _context.Database.GetDbConnection();
        try
        {
            await _context.Database.OpenConnectionAsync();
            using var cmd = connection.CreateCommand();
            cmd.CommandText = sql;
            using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                var title = reader.IsDBNull(0) ? "" : reader.GetString(0).Trim();
                if (!string.IsNullOrWhiteSpace(title))
                    rawTitles.Add(title);
            }
        }
        finally
        {
            await _context.Database.CloseConnectionAsync();
        }

        // Strip Roman numeral level suffixes (I through X) from the end
        var romanNumerals = new[] { " X", " IX", " VIII", " VII", " VI", " V", " IV", " III", " II", " I" };
        var baseTitles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var title in rawTitles)
        {
            var baseTitle = title;
            foreach (var suffix in romanNumerals)
            {
                if (baseTitle.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
                {
                    baseTitle = baseTitle[..^suffix.Length].TrimEnd();
                    break;
                }
            }
            baseTitles.Add(baseTitle);
        }

        var result = baseTitles.ToList();
        result.Sort(StringComparer.OrdinalIgnoreCase);
        return result;
    }

    // -----------------------------------------------------------------------
    // Private helper methods
    // -----------------------------------------------------------------------

    private async Task<IgceMethodResult?> EstimateByHistoricalAnalogAsync(IgceRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.NaicsCode))
            return null;

        var fiveYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-5));

        // Historical analog uses usaspending_award (authoritative source for award trend analysis)
        // Filter by NAICS only — agency name formats differ between opportunity and USASpending
        // (e.g., "STATE, DEPARTMENT OF" vs "Department of State"), so agency is used as a
        // soft preference rather than a hard filter.
        var query = _context.UsaspendingAwards.AsNoTracking()
            .Where(a => a.NaicsCode == request.NaicsCode
                        && a.StartDate != null
                        && a.StartDate >= fiveYearsAgo
                        && a.BaseAndAllOptionsValue != null
                        && a.BaseAndAllOptionsValue > 0);

        var values = await query
            .Select(a => a.BaseAndAllOptionsValue!.Value)
            .ToListAsync();

        if (values.Count == 0)
            return null;

        var avg = Math.Round(values.Average(), 2);
        var confidence = values.Count switch
        {
            >= 50 => 0.8m,
            >= 20 => 0.6m,
            >= 10 => 0.4m,
            _ => 0.2m
        };

        return new IgceMethodResult
        {
            MethodName = "Historical Analog",
            Estimate = avg,
            Confidence = confidence,
            Explanation = $"Average of {values.Count} comparable awards in NAICS {request.NaicsCode} over last 5 years",
            DataPoints = values.Count
        };
    }

    private async Task<IgceMethodResult?> EstimateByLaborBottomsUpAsync(IgceRequest request)
    {
        if (request.LaborMix == null || request.LaborMix.Count == 0)
            return null;

        // FIX 3: Batch all canonical IDs into a single query to avoid N+1
        var canonicalIds = request.LaborMix.Select(item => item.CanonicalId).Distinct().ToList();

        var allRates = await _context.LaborCategoryMappings
            .AsNoTracking()
            .Where(m => m.CanonicalId.HasValue && canonicalIds.Contains(m.CanonicalId.Value) && m.Source == "GSA_CALC")
            .Join(_context.GsaLaborRates.AsNoTracking(),
                m => m.RawLaborCategory,
                g => g.LaborCategory,
                (m, g) => new { m.CanonicalId, Price = g.CurrentPrice })
            .Where(x => x.Price != null && x.Price > 0)
            .Select(x => new { CanonicalId = x.CanonicalId!.Value, Price = x.Price!.Value })
            .ToListAsync();

        // Group by canonical ID and compute median for each
        var medianByCanonical = allRates
            .GroupBy(x => x.CanonicalId)
            .ToDictionary(
                g => g.Key,
                g =>
                {
                    var sorted = g.Select(x => x.Price).OrderBy(p => p).ToList();
                    return new { MedianRate = Percentile(sorted, 50), Count = sorted.Count };
                });

        decimal totalEstimate = 0;
        int dataPoints = 0;

        foreach (var item in request.LaborMix)
        {
            if (!medianByCanonical.TryGetValue(item.CanonicalId, out var rateInfo))
                continue;

            totalEstimate += rateInfo.MedianRate * item.Hours;
            dataPoints += rateInfo.Count;
        }

        if (dataPoints == 0)
            return null;

        // Apply POP multiplier if provided (annualize and scale)
        if (request.PopMonths.HasValue && request.PopMonths > 0)
        {
            // Labor mix hours are assumed to be annual; scale to full POP
            totalEstimate = totalEstimate * request.PopMonths.Value / 12m;
        }

        return new IgceMethodResult
        {
            MethodName = "Labor Bottoms-Up",
            Estimate = Math.Round(totalEstimate, 2),
            Confidence = 0.7m,
            Explanation = $"GSA median rates x estimated hours for {request.LaborMix.Count} labor categories",
            DataPoints = dataPoints
        };
    }

    private async Task<IgceMethodResult?> EstimateByBurnRateAsync(IgceRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.NoticeId))
            return null;

        // Find the opportunity's linked contract via solicitation number
        var opportunity = await _context.Opportunities
            .AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == request.NoticeId);

        if (opportunity == null || string.IsNullOrWhiteSpace(opportunity.SolicitationNumber))
            return null;

        // Use usaspending_award for burn rate analysis (authoritative spending source)
        var award = await _context.UsaspendingAwards
            .AsNoTracking()
            .Where(a => a.SolicitationIdentifier == opportunity.SolicitationNumber
                        && a.TotalObligation != null
                        && a.StartDate != null)
            .OrderByDescending(a => a.StartDate)
            .FirstOrDefaultAsync();

        if (award == null)
            return null;

        var monthsElapsed = (DateTime.UtcNow - award.StartDate!.Value.ToDateTime(TimeOnly.MinValue)).TotalDays / 30.0;
        if (monthsElapsed <= 0)
            return null;

        var monthlyBurnRate = award.TotalObligation!.Value / (decimal)monthsElapsed;

        var popMonths = request.PopMonths ?? 12;
        var estimate = Math.Round(monthlyBurnRate * popMonths, 2);

        return new IgceMethodResult
        {
            MethodName = "Burn Rate Extrapolation",
            Estimate = estimate,
            Confidence = 0.5m,
            Explanation = $"Incumbent burn rate ${monthlyBurnRate:N0}/month x {popMonths} months POP",
            DataPoints = 1
        };
    }

    /// <summary>
    /// Supplementary FPDS query for competition stats (NumberOfOffers is FPDS-only).
    /// Award value stats come from the USASpending results passed in.
    /// </summary>
    private async Task<CompetitionStatsDto> GetCompetitionStatsFromFpdsAsync(
        string naicsCode, DateOnly fiveYearsAgo, string? escapedAgency,
        List<decimal> usaValues, decimal medianAwardValue)
    {
        var fpdsQuery = _context.FpdsContracts.AsNoTracking()
            .Where(c => c.NaicsCode == naicsCode
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= fiveYearsAgo
                        && c.NumberOfOffers != null
                        && c.NumberOfOffers > 0);

        if (escapedAgency != null)
            fpdsQuery = fpdsQuery.Where(c => c.AgencyName != null && EF.Functions.Like(c.AgencyName, $"%{escapedAgency}%"));

        var fpdsOffers = await fpdsQuery
            .Select(c => c.NumberOfOffers!.Value)
            .Take(500)
            .ToListAsync();

        var offersList = fpdsOffers.Select(o => (decimal)o).OrderBy(o => o).ToList();
        var soloSourceCount = fpdsOffers.Count(o => o == 1);

        return new CompetitionStatsDto
        {
            AvgOffers = offersList.Count > 0 ? Math.Round(offersList.Average(), 2) : 0,
            MedianOffers = offersList.Count > 0 ? Percentile(offersList, 50) : 0,
            SoloSourcePct = fpdsOffers.Count > 0 ? Math.Round((decimal)soloSourceCount / fpdsOffers.Count * 100, 2) : 0,
            AvgAwardValue = usaValues.Count > 0 ? Math.Round(usaValues.Average(), 2) : 0,
            MedianAwardValue = medianAwardValue
        };
    }

    /// <summary>
    /// Escape LIKE wildcard characters in user input to prevent unintended pattern matching.
    /// </summary>
    private static string EscapeLikeWildcards(string input)
    {
        return input.Replace("%", "\\%").Replace("_", "\\_");
    }

    /// <summary>
    /// Compute the p-th percentile from a sorted list of values.
    /// </summary>
    private static decimal Percentile(List<decimal> sortedValues, int percentile)
    {
        if (sortedValues.Count == 0) return 0m;
        if (sortedValues.Count == 1) return sortedValues[0];

        var index = (percentile / 100.0) * (sortedValues.Count - 1);
        var lower = (int)Math.Floor(index);
        var upper = (int)Math.Ceiling(index);

        if (lower == upper)
            return Math.Round(sortedValues[lower], 2);

        var fraction = (decimal)(index - lower);
        return Math.Round(sortedValues[lower] + fraction * (sortedValues[upper] - sortedValues[lower]), 2);
    }
}
