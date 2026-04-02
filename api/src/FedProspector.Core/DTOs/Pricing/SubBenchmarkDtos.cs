namespace FedProspector.Core.DTOs.Pricing;

public class SubBenchmarkRequest
{
    public string? NaicsCode { get; set; }
    public string? AgencyName { get; set; }
}

public class SubBenchmarkDto
{
    public string? NaicsCode { get; set; }
    public string? AgencyName { get; set; }
    public string? SubBusinessType { get; set; }
    public int SubCount { get; set; }
    public decimal TotalValue { get; set; }
    public decimal AvgValue { get; set; }
    public decimal MinValue { get; set; }
    public decimal MaxValue { get; set; }
}

public class SubRatioDto
{
    public string? NaicsCode { get; set; }
    public decimal AvgSubRatio { get; set; }
    public decimal MedianSubRatio { get; set; }
    public int Count { get; set; }
}
