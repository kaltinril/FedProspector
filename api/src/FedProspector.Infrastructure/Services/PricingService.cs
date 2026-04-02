using FedProspector.Core.DTOs.Pricing;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class PricingService : IPricingService
{
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
            .Where(m => m.CanonicalId == canonicalId)
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

        var values = awards
            .Select(a => a.BaseAndAllOptionsValue!.Value)
            .OrderBy(v => v)
            .ToList();

        var p25 = Percentile(values, 25);
        var p50 = Percentile(values, 50);
        var p75 = Percentile(values, 75);

        // Competition stats from FPDS supplement (NumberOfOffers is FPDS-only)
        var competitionStats = await GetCompetitionStatsFromFpdsAsync(
            request.NaicsCode, fiveYearsAgo, escapedAgency, values, p50);

        // Top 20 comparable awards
        var comparableAwards = awards.Take(20).Select(a =>
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
        var confidence = awards.Count switch
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
            TargetEstimate = p50,
            HighEstimate = p75,
            Confidence = confidence,
            ComparableCount = awards.Count,
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
            .Where(m => m.CanonicalId == request.CanonicalId)
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
        // Auto-populate from opportunity if NoticeId provided but NAICS/Agency missing
        if (!string.IsNullOrWhiteSpace(request.NoticeId)
            && string.IsNullOrWhiteSpace(request.NaicsCode))
        {
            // Support both notice_id and solicitation_number lookups
            var opp = await _context.Opportunities.AsNoTracking()
                .FirstOrDefaultAsync(o => o.NoticeId == request.NoticeId
                    || o.SolicitationNumber == request.NoticeId);

            if (opp != null)
            {
                request.NaicsCode ??= opp.NaicsCode;
                request.AgencyName ??= opp.DepartmentName;
                // Use internal notice_id for burn rate lookup
                request.NoticeId = opp.NoticeId;
            }
        }

        var methods = new List<IgceMethodResult>();

        // Method 1: Historical analog -- average of comparable past awards
        var analogEstimate = await EstimateByHistoricalAnalogAsync(request);
        if (analogEstimate != null)
            methods.Add(analogEstimate);

        // Method 2: Labor bottoms-up -- labor categories x median GSA rates x hours
        var laborEstimate = await EstimateByLaborBottomsUpAsync(request);
        if (laborEstimate != null)
            methods.Add(laborEstimate);

        // Method 3: Burn rate extrapolation -- incumbent monthly burn rate x new POP
        var burnRateEstimate = await EstimateByBurnRateAsync(request);
        if (burnRateEstimate != null)
            methods.Add(burnRateEstimate);

        if (methods.Count == 0)
        {
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

    // -----------------------------------------------------------------------
    // Private helper methods
    // -----------------------------------------------------------------------

    private async Task<IgceMethodResult?> EstimateByHistoricalAnalogAsync(IgceRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.NaicsCode))
            return null;

        var fiveYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-5));

        // Historical analog uses usaspending_award (authoritative source for award trend analysis)
        var query = _context.UsaspendingAwards.AsNoTracking()
            .Where(a => a.NaicsCode == request.NaicsCode
                        && a.StartDate != null
                        && a.StartDate >= fiveYearsAgo
                        && a.BaseAndAllOptionsValue != null
                        && a.BaseAndAllOptionsValue > 0);

        if (!string.IsNullOrWhiteSpace(request.AgencyName))
        {
            var escapedAgency = EscapeLikeWildcards(request.AgencyName);
            query = query.Where(a => a.AwardingAgencyName != null && EF.Functions.Like(a.AwardingAgencyName, $"%{escapedAgency}%"));
        }

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
            .Where(m => m.CanonicalId.HasValue && canonicalIds.Contains(m.CanonicalId.Value))
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
