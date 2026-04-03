using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class CertificationExpirationAlertView
{
    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("certification_type")]
    public string CertificationType { get; set; } = string.Empty;

    [Column("expiration_date")]
    public DateTime ExpirationDate { get; set; }

    [Column("days_until_expiration")]
    public int DaysUntilExpiration { get; set; }

    [Column("alert_level")]
    public string AlertLevel { get; set; } = string.Empty;

    [Column("source")]
    public string Source { get; set; } = string.Empty;
}
