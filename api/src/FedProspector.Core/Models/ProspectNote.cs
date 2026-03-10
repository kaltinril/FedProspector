using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

[Table("prospect_note")]
public class ProspectNote
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int NoteId { get; set; }

    [Required]
    public int ProspectId { get; set; }

    [Required]
    public int UserId { get; set; }

    [MaxLength(30)]
    public string? NoteType { get; set; } = "COMMENT";

    [Required]
    public string NoteText { get; set; } = string.Empty;

    public DateTime? CreatedAt { get; set; }

    // Navigation properties
    [ForeignKey("ProspectId")]
    public Prospect? Prospect { get; set; }

    [ForeignKey("UserId")]
    public AppUser? User { get; set; }
}
