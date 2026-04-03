using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class DataFreshnessView
{
    [Column("source_name")]
    public string SourceName { get; set; } = string.Empty;

    [Column("last_load_date")]
    public DateTime? LastLoadDate { get; set; }

    [Column("records_loaded")]
    public int RecordsLoaded { get; set; }

    [Column("last_load_status")]
    public string? LastLoadStatus { get; set; }

    [Column("hours_since_last_load")]
    public int? HoursSinceLastLoad { get; set; }

    [Column("freshness_status")]
    public string FreshnessStatus { get; set; } = string.Empty;

    [Column("table_row_count")]
    public long? TableRowCount { get; set; }

    [Column("table_name")]
    public string? TableName { get; set; }
}
