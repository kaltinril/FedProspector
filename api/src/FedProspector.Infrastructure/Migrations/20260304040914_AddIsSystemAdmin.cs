using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FedProspector.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddIsSystemAdmin : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<bool>(
                name: "is_system_admin",
                table: "app_user",
                type: "tinyint(1)",
                nullable: false,
                defaultValue: false);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "is_system_admin",
                table: "app_user");
        }
    }
}
