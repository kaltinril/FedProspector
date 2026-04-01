namespace FedProspector.Core.DTOs.Intelligence;

public class PursuitPriorityDto
{
    public string NoticeId { get; set; } = "";
    /// <summary>Combined pursuit priority score (0-100).</summary>
    public decimal PursuitScore { get; set; }
    /// <summary>MustPursue (>=75), ShouldPursue (50-74), Consider (30-49), Skip (&lt;30).</summary>
    public string Category { get; set; } = "";
    public decimal PWinScore { get; set; }
    public string PWinConfidence { get; set; } = "";
    public decimal OqScore { get; set; }
    public string OqConfidence { get; set; } = "";
    /// <summary>True if either pWin or OQS confidence was Low, causing a 15% score discount.</summary>
    public bool ConfidenceDiscountApplied { get; set; }
    /// <summary>HighPWin_HighOQS, HighPWin_LowOQS, LowPWin_HighOQS, LowPWin_LowOQS.</summary>
    public string Quadrant { get; set; } = "";
}
