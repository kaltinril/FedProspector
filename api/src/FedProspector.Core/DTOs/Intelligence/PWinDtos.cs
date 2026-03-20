namespace FedProspector.Core.DTOs.Intelligence;

public class PWinResultDto
{
    public int? ProspectId { get; set; }
    public string NoticeId { get; set; } = "";
    public decimal Score { get; set; }
    public string Category { get; set; } = "";
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
