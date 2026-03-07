namespace FedProspector.Core.DTOs.Intelligence;

public class QualificationCheckDto
{
    public string NoticeId { get; set; } = "";
    public int PassCount { get; set; }
    public int FailCount { get; set; }
    public int WarningCount { get; set; }
    public int TotalChecks { get; set; }
    public string OverallStatus { get; set; } = "";  // "Qualified", "Partially Qualified", "Not Qualified"
    public List<QualificationItemDto> Checks { get; set; } = new();
}

public class QualificationItemDto
{
    public string Name { get; set; } = "";
    public string Category { get; set; } = "";  // "Certification", "Experience", "Compliance", "Logistics"
    public string Status { get; set; } = "";     // "Pass", "Fail", "Warning", "Unknown"
    public string Detail { get; set; } = "";
}
