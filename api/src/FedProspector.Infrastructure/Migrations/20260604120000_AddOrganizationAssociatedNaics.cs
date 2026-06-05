using System;
using Microsoft.EntityFrameworkCore.Metadata;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FedProspector.Infrastructure.Migrations
{
    /// <summary>
    /// Phase 136 Unit G: Associated NAICS (manual, user-prioritized list beyond the org's
    /// registered + linked-entity codes). Creates the EF-Core-owned app table
    /// organization_associated_naics with a unique key on (organization_id, naics_code).
    ///
    /// NO foreign key to organization (project convention — organization_id references the
    /// org logically). The authoritative prod apply is the idempotent raw-SQL migration
    /// fed_prospector/db/schema/migrations/136_organization_associated_naics.sql; keep this
    /// migration, the snapshot, the raw SQL, and the DDL in 90_web_api.sql in sync.
    ///
    /// DO NOT run `dotnet ef database update` for this — it is applied to dev + prod by hand.
    /// </summary>
    public partial class AddOrganizationAssociatedNaics : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "organization_associated_naics",
                columns: table => new
                {
                    id = table.Column<int>(type: "int", nullable: false)
                        .Annotation("MySql:ValueGenerationStrategy", MySqlValueGenerationStrategy.IdentityColumn),
                    organization_id = table.Column<int>(type: "int", nullable: false),
                    naics_code = table.Column<string>(type: "varchar(11)", maxLength: 11, nullable: false)
                        .Annotation("MySql:CharSet", "utf8mb4"),
                    note = table.Column<string>(type: "longtext", nullable: true)
                        .Annotation("MySql:CharSet", "utf8mb4"),
                    created_at = table.Column<DateTime>(type: "datetime(6)", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_organization_associated_naics", x => x.id);
                })
                .Annotation("MySql:CharSet", "utf8mb4");

            migrationBuilder.CreateIndex(
                name: "ix_organization_associated_naics_organization_id_naics_code",
                table: "organization_associated_naics",
                columns: new[] { "organization_id", "naics_code" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "organization_associated_naics");
        }
    }
}
