namespace FedProspector.Core.DTOs.Prospects;

public class AutoProspectRequest
{
    public int? OrganizationId { get; set; }
}

public class AutoProspectResult
{
    public int Evaluated { get; set; }
    public int Created { get; set; }
    public int Skipped { get; set; }
    public List<string> Errors { get; set; } = [];
    public List<AutoProspectSearchResult> SearchResults { get; set; } = [];
}

public class AutoProspectSearchResult
{
    public int SearchId { get; set; }
    public string SearchName { get; set; } = string.Empty;
    public int Candidates { get; set; }
    public int Created { get; set; }
}
