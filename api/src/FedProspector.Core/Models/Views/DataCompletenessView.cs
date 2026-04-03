using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class DataCompletenessView
{
    [Column("table_name")]
    public string TableName { get; set; } = string.Empty;

    [Column("total_rows")]
    public long TotalRows { get; set; }

    [Column("field_name")]
    public string FieldName { get; set; } = string.Empty;

    [Column("non_null_count")]
    public long NonNullCount { get; set; }

    [Column("null_count")]
    public long NullCount { get; set; }

    [Column("completeness_pct")]
    public decimal CompletenessPct { get; set; }
}
