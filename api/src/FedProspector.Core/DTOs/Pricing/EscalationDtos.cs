namespace FedProspector.Core.DTOs.Pricing;

public class RateTrendRequest
{
    public int CanonicalId { get; set; }
    public int Years { get; set; } = 5;
}

public class RateTrendDto
{
    public int Year { get; set; }
    public decimal AvgRate { get; set; }
    public decimal MinRate { get; set; }
    public decimal MaxRate { get; set; }
    public int RateCount { get; set; }
    public decimal? YoyChangePct { get; set; }
}

public class EscalationForecastDto
{
    public int Year { get; set; }
    public decimal ProjectedRate { get; set; }
    public decimal ConfidenceLow { get; set; }
    public decimal ConfidenceHigh { get; set; }
    public decimal? BlsEciIndex { get; set; }
    public string Method { get; set; } = "";
}
