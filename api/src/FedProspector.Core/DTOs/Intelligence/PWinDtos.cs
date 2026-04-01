namespace FedProspector.Core.DTOs.Intelligence;

public class PWinResultDto
{
    public int? ProspectId { get; set; }
    public string NoticeId { get; set; } = "";
    public decimal Score { get; set; }
    public string Category { get; set; } = "";
    /// <summary>High, Medium, or Low — based on how many factors had real data vs. defaults.</summary>
    public string Confidence { get; set; } = "Medium";
    /// <summary>Percentage of factors that had real data (0-100).</summary>
    public int DataCompletenessPercent { get; set; }
    public List<PWinFactorDto> Factors { get; set; } = new();
    public List<string> Suggestions { get; set; } = new();
}

public class PWinFactorDto
{
    public string Name { get; set; } = "";
    public decimal Score { get; set; }
    public decimal Weight { get; set; }
    public decimal WeightedScore { get; set; }
    public string Detail { get; set; } = "";
    /// <summary>Whether this factor was scored with real data (true) or fell back to a default (false).</summary>
    public bool HadRealData { get; set; } = true;
}

public class BatchPWinRequest
{
    public List<string> NoticeIds { get; set; } = new();
}

public class BatchPWinResponse
{
    public Dictionary<string, BatchPWinEntry?> Results { get; set; } = new();
}

public class BatchPWinEntry
{
    public decimal Score { get; set; }
    public string Category { get; set; } = "";
}
