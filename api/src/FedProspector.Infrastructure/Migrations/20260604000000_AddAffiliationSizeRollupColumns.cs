using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FedProspector.Infrastructure.Migrations
{
    /// <summary>
    /// Phase 133 Task 6: SBA Affiliation Size Roll-Up (13 CFR 121.103).
    /// Adds four nullable/defaulted columns to organization_entity for affiliation-aware
    /// size determination. organization_entity is EF Core-owned.
    ///
    /// Scoped intentionally to ONLY these four columns. The EF model snapshot predates
    /// several later-phase (Python-DDL-owned) tables/columns; a full auto-scaffold would
    /// bundle that unrelated drift. The authoritative prod apply is the idempotent raw-SQL
    /// migration fed_prospector/db/schema/migrations/133b_affiliation_size_rollup_columns.sql;
    /// keep all three (this migration, the snapshot, the raw SQL, and the DDL in 90_web_api.sql)
    /// in sync.
    /// </summary>
    public partial class AddAffiliationSizeRollupColumns : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<decimal>(
                name: "affiliate_annual_revenue",
                table: "organization_entity",
                type: "decimal(18,2)",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "affiliate_employee_count",
                table: "organization_entity",
                type: "int",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "mpa_approved",
                table: "organization_entity",
                type: "varchar(1)",
                maxLength: 1,
                nullable: false,
                defaultValue: "N")
                .Annotation("MySql:CharSet", "utf8mb4");

            migrationBuilder.AddColumn<DateOnly>(
                name: "mpa_effective_date",
                table: "organization_entity",
                type: "date",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "affiliate_annual_revenue",
                table: "organization_entity");

            migrationBuilder.DropColumn(
                name: "affiliate_employee_count",
                table: "organization_entity");

            migrationBuilder.DropColumn(
                name: "mpa_approved",
                table: "organization_entity");

            migrationBuilder.DropColumn(
                name: "mpa_effective_date",
                table: "organization_entity");
        }
    }
}
