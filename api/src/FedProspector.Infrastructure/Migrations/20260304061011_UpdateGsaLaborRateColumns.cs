using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FedProspector.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class UpdateGsaLaborRateColumns : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "description",
                table: "opportunity");

            migrationBuilder.DropColumn(
                name: "hourly_rate_year1",
                table: "gsa_labor_rate");

            migrationBuilder.AddColumn<string>(
                name: "description_url",
                table: "opportunity",
                type: "varchar(500)",
                maxLength: 500,
                nullable: true)
                .Annotation("MySql:CharSet", "utf8mb4");

            migrationBuilder.AddColumn<string>(
                name: "category",
                table: "gsa_labor_rate",
                type: "varchar(200)",
                maxLength: 200,
                nullable: true)
                .Annotation("MySql:CharSet", "utf8mb4");

            migrationBuilder.AddColumn<string>(
                name: "idv_piid",
                table: "gsa_labor_rate",
                type: "varchar(50)",
                maxLength: 50,
                nullable: true)
                .Annotation("MySql:CharSet", "utf8mb4");

            migrationBuilder.AddColumn<string>(
                name: "subcategory",
                table: "gsa_labor_rate",
                type: "varchar(500)",
                maxLength: 500,
                nullable: true)
                .Annotation("MySql:CharSet", "utf8mb4");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "description_url",
                table: "opportunity");

            migrationBuilder.DropColumn(
                name: "category",
                table: "gsa_labor_rate");

            migrationBuilder.DropColumn(
                name: "idv_piid",
                table: "gsa_labor_rate");

            migrationBuilder.DropColumn(
                name: "subcategory",
                table: "gsa_labor_rate");

            migrationBuilder.AddColumn<string>(
                name: "description",
                table: "opportunity",
                type: "longtext",
                nullable: true)
                .Annotation("MySql:CharSet", "utf8mb4");

            migrationBuilder.AddColumn<decimal>(
                name: "hourly_rate_year1",
                table: "gsa_labor_rate",
                type: "decimal(10,2)",
                nullable: true);
        }
    }
}
