namespace FedProspector.Core.DTOs.Pricing;

public class RateHeatmapRequest
{
    public string? CategoryGroup { get; set; }
    public string? Worksite { get; set; }
    public string? EducationLevel { get; set; }
}

public class RateHeatmapCell
{
    public string CanonicalName { get; set; } = "";
    public string? CategoryGroup { get; set; }
    public string? Worksite { get; set; }
    public string? EducationLevel { get; set; }
    public int RateCount { get; set; }
    public decimal MinRate { get; set; }
    public decimal AvgRate { get; set; }
    public decimal MaxRate { get; set; }
    public decimal P25Rate { get; set; }
    public decimal MedianRate { get; set; }
    public decimal P75Rate { get; set; }
}

public class RateDistributionDto
{
    public int CanonicalId { get; set; }
    public string CanonicalName { get; set; } = "";
    public List<decimal> Rates { get; set; } = new();
    public int Count { get; set; }
    public decimal MinRate { get; set; }
    public decimal P25Rate { get; set; }
    public decimal MedianRate { get; set; }
    public decimal P75Rate { get; set; }
    public decimal MaxRate { get; set; }
    public decimal AvgRate { get; set; }
}
