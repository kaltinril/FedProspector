using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("contracting_officer")]
public class ContractingOfficer
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int OfficerId { get; set; }

    [Required]
    [MaxLength(200)]
    public string FullName { get; set; } = string.Empty;

    [MaxLength(200)]
    public string? Email { get; set; }

    [MaxLength(50)]
    public string? Phone { get; set; }

    [MaxLength(50)]
    public string? Fax { get; set; }

    [MaxLength(200)]
    public string? Title { get; set; }

    [MaxLength(200)]
    public string? DepartmentName { get; set; }

    [MaxLength(200)]
    public string? OfficeName { get; set; }

    [MaxLength(50)]
    public string? OfficerType { get; set; }

    public DateTime? CreatedAt { get; set; }

    public DateTime? UpdatedAt { get; set; }
}
