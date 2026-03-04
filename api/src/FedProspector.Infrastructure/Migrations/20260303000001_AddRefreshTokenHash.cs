using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FedProspector.Infrastructure.Migrations;

/// <inheritdoc />
public partial class AddRefreshTokenHash : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>(
            name: "refresh_token_hash",
            table: "app_session",
            type: "varchar(64)",
            maxLength: 64,
            nullable: true);

        migrationBuilder.CreateIndex(
            name: "IX_app_session_refresh_token_hash",
            table: "app_session",
            column: "refresh_token_hash");
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropIndex(
            name: "IX_app_session_refresh_token_hash",
            table: "app_session");

        migrationBuilder.DropColumn(
            name: "refresh_token_hash",
            table: "app_session");
    }
}
