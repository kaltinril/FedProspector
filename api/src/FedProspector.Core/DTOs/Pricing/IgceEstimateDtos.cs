namespace FedProspector.Core.DTOs.Pricing;

public class IgceRequest
{
    public string? NoticeId { get; set; }
    public string? NaicsCode { get; set; }
    public string? AgencyName { get; set; }
    public int? PopMonths { get; set; }
    public List<LaborMixItem>? LaborMix { get; set; }
}

public class LaborMixItem
{
    public int CanonicalId { get; set; }
    public int Hours { get; set; }
}

public class IgceResponse
{
    public List<IgceMethodResult> Methods { get; set; } = new();
    public decimal WeightedEstimate { get; set; }
    public string ConfidenceLevel { get; set; } = "";
}

public class IgceMethodResult
{
    public string MethodName { get; set; } = "";
    public decimal Estimate { get; set; }
    public decimal Confidence { get; set; }
    public string Explanation { get; set; } = "";
    public int DataPoints { get; set; }
}
