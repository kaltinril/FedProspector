using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class MentorProtegeCandidateView
{
    [Column("protege_uei")]
    public string ProtegeUei { get; set; } = string.Empty;

    [Column("protege_name")]
    public string? ProtegeName { get; set; }

    [Column("protege_certifications")]
    public string? ProtegeCertifications { get; set; }

    [Column("protege_naics")]
    public string? ProtegeNaics { get; set; }

    [Column("protege_contract_count")]
    public int ProtegeContractCount { get; set; }

    [Column("protege_total_value")]
    public decimal ProtegeTotalValue { get; set; }

    [Column("mentor_uei")]
    public string MentorUei { get; set; } = string.Empty;

    [Column("mentor_name")]
    public string? MentorName { get; set; }

    [Column("shared_naics")]
    public string? SharedNaics { get; set; }

    [Column("mentor_contract_count")]
    public int MentorContractCount { get; set; }

    [Column("mentor_total_value")]
    public decimal MentorTotalValue { get; set; }

    [Column("mentor_agencies")]
    public string? MentorAgencies { get; set; }
}
