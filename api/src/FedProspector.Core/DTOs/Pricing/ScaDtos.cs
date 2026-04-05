namespace FedProspector.Core.DTOs.Pricing;

// ---- Rate Range ----

public class RateRangeRequest
{
    public int CanonicalId { get; set; }
    public string? State { get; set; }
    public string? County { get; set; }
}

public class RateRangeResponse
{
    public int CanonicalId { get; set; }
    public string CanonicalName { get; set; } = "";
    public string? Area { get; set; }
    public decimal? ScaFloorRate { get; set; }
    public decimal? ScaFringe { get; set; }
    public decimal? ScaFullCost { get; set; }
    public decimal? GsaCeilingRate { get; set; }
    public decimal? GsaP25Rate { get; set; }
    public decimal? GsaP75Rate { get; set; }
    public decimal? Spread { get; set; }
    public decimal? SpreadPct { get; set; }
    public int GsaRateCount { get; set; }
    public string? WdNumber { get; set; }
    public DateTime? WdEffectiveDate { get; set; }
}

// ---- SCA Compliance Check ----

public class ScaComplianceRequest
{
    public string? State { get; set; }
    public string? County { get; set; }
    public List<ScaComplianceLineItem> LineItems { get; set; } = new();
}

public class ScaComplianceLineItem
{
    public int CanonicalId { get; set; }
    public decimal ProposedRate { get; set; }
    public bool IncludesFringe { get; set; }
}

public class ScaComplianceResponse
{
    public bool AllCompliant { get; set; }
    public int CompliantCount { get; set; }
    public int ViolationCount { get; set; }
    public int UnmappedCount { get; set; }
    public decimal TotalFringeObligation { get; set; }
    public List<ScaComplianceResult> Results { get; set; } = new();
}

public class ScaComplianceResult
{
    public int CanonicalId { get; set; }
    public string CanonicalName { get; set; } = "";
    public decimal ProposedRate { get; set; }
    public decimal? ScaMinimumRate { get; set; }
    public decimal? ScaFringe { get; set; }
    public decimal? ScaFullCost { get; set; }
    public string Status { get; set; } = "";
    public decimal? Shortfall { get; set; }
    public string? WdNumber { get; set; }
}

// ---- SCA Area Rates ----

public class ScaAreaRateRequest
{
    public string? OccupationTitle { get; set; }
    public string? State { get; set; }
    public string? County { get; set; }
    public string? WdNumber { get; set; }
    public string? AreaName { get; set; }
}

public class ScaAreaRateDto
{
    public string State { get; set; } = "";
    public string? County { get; set; }
    public string AreaName { get; set; } = "";
    public string OccupationCode { get; set; } = "";
    public string OccupationTitle { get; set; } = "";
    public decimal HourlyRate { get; set; }
    public decimal Fringe { get; set; }
    public decimal FullCost { get; set; }
    public string? WdNumber { get; set; }
    public int? Revision { get; set; }
    public DateTime? EffectiveDate { get; set; }
}
