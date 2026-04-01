namespace FedProspector.Core.DTOs.Intelligence;

public class OpenDoorAnalysisDto
{
    public string NaicsCode { get; set; } = "";
    public int YearsAnalyzed { get; set; }
    public int TotalPrimesFound { get; set; }
    public List<OpenDoorScoreDto> Primes { get; set; } = new();
}

public class OpenDoorScoreDto
{
    public string PrimeUei { get; set; } = "";
    public string PrimeName { get; set; } = "";
    public int OpenDoorScore { get; set; }
    public string Category { get; set; } = "";
    public string Confidence { get; set; } = "Medium";
    public int DataCompletenessPercent { get; set; }
    public List<OpenDoorFactorDto> Factors { get; set; } = new();
    public int TotalSubawards { get; set; }
    public int DistinctSubs { get; set; }
    public decimal TotalSubValue { get; set; }
}

public class OpenDoorFactorDto
{
    public string Name { get; set; } = "";
    public int Score { get; set; }
    public decimal Weight { get; set; }
    public decimal WeightedScore { get; set; }
    public string Detail { get; set; } = "";
    public bool HadRealData { get; set; } = true;
}
