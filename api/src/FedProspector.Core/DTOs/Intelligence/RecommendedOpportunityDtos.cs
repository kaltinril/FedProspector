namespace FedProspector.Core.DTOs.Intelligence;

public class RecommendedOpportunityDto
{
    public string NoticeId { get; set; } = "";
    public string? Title { get; set; }
    public string? SolicitationNumber { get; set; }
    public string? DepartmentName { get; set; }
    public string? SubTier { get; set; }
    public string? ContractingOfficeId { get; set; }
    public string? SetAsideCode { get; set; }
    public string? SetAsideDescription { get; set; }
    public string? NaicsCode { get; set; }
    public string? NaicsDescription { get; set; }
    public string? ClassificationCode { get; set; }
    public string? NoticeType { get; set; }
    public decimal? AwardAmount { get; set; }
    public DateTime? PostedDate { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public int? DaysRemaining { get; set; }
    public string? PopState { get; set; }
    public string? PopCity { get; set; }
    public string? PopCountry { get; set; }
    public int? FhOrgId { get; set; }

    // OQS scoring (new 7-factor weighted model)
    /// <summary>Opportunity Quality Score (0-100), weighted sum of 7 factors.</summary>
    public decimal OqScore { get; set; }
    /// <summary>Category derived from OqScore: High (>=70), Medium (40-69), Low (15-39), VeryLow (&lt;15).</summary>
    public string OqScoreCategory { get; set; } = "";
    /// <summary>Breakdown of all OQS factor scores and weights.</summary>
    public List<OqScoreFactorDto> OqScoreFactors { get; set; } = new();
    /// <summary>Data confidence: High (>=6 factors with real data), Medium (>=4), Low (&lt;4).</summary>
    public string Confidence { get; set; } = "Medium";

    // Backward compatibility — delegates to OQS properties
    [Obsolete("Use OqScore instead")]
    public decimal QScore { get => OqScore; set => OqScore = value; }
    [Obsolete("Use OqScoreCategory instead")]
    public string QScoreCategory { get => OqScoreCategory; set => OqScoreCategory = value; }
    [Obsolete("Use OqScoreFactors instead")]
    public List<QScoreFactorDto> QScoreFactors
    {
        get => OqScoreFactors.Select(f => new QScoreFactorDto
        {
            Name = f.Name,
            Points = f.WeightedScore,
            MaxPoints = f.Weight * 100
        }).ToList();
        set { } // no-op for deserialization compat
    }

    // Re-compete indicator
    public bool IsRecompete { get; set; }
    public string? IncumbentName { get; set; }
}

/// <summary>Factor detail for the 7-factor OQS model.</summary>
public class OqScoreFactorDto
{
    /// <summary>Human-readable factor name.</summary>
    public string Name { get; set; } = "";
    /// <summary>Raw score for this factor (0-100).</summary>
    public int Score { get; set; }
    /// <summary>Weight of this factor (all weights sum to 1.0).</summary>
    public decimal Weight { get; set; }
    /// <summary>Score * Weight contribution to final OQS.</summary>
    public decimal WeightedScore { get; set; }
    /// <summary>Human-readable explanation of why this score was assigned.</summary>
    public string Detail { get; set; } = "";
    /// <summary>True if real data was available; false if a default/fallback was used.</summary>
    public bool HadRealData { get; set; } = true;
}

[Obsolete("Use OqScoreFactorDto instead")]
public class QScoreFactorDto
{
    public string Name { get; set; } = "";
    public decimal Points { get; set; }
    public decimal MaxPoints { get; set; }
}
