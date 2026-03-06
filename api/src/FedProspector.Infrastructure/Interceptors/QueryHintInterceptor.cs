using System.Data.Common;
using System.Text.RegularExpressions;
using Microsoft.EntityFrameworkCore.Diagnostics;

namespace FedProspector.Infrastructure.Interceptors;

/// <summary>
/// Converts EF Core TagWith("HINT:...") comments into MySQL optimizer hints.
/// Usage: query.TagWith("HINT:NO_INDEX(entity idx_entity_name)")
/// Result: SELECT /*+ NO_INDEX(entity idx_entity_name) */ ... (tag comment removed)
/// </summary>
public partial class QueryHintInterceptor : DbCommandInterceptor
{
    // Matches: -- HINT:NO_INDEX(entity idx_entity_name)  (or any valid hint)
    [GeneratedRegex(@"-- HINT:([A-Z_]+\([^)]+\))\r?\n?", RegexOptions.Compiled)]
    private static partial Regex HintTagPattern();

    public override InterceptionResult<DbDataReader> ReaderExecuting(
        DbCommand command, CommandEventData eventData, InterceptionResult<DbDataReader> result)
    {
        ApplyHints(command);
        return result;
    }

    public override ValueTask<InterceptionResult<DbDataReader>> ReaderExecutingAsync(
        DbCommand command, CommandEventData eventData, InterceptionResult<DbDataReader> result,
        CancellationToken cancellationToken = default)
    {
        ApplyHints(command);
        return ValueTask.FromResult(result);
    }

    private static void ApplyHints(DbCommand command)
    {
        var sql = command.CommandText;
        var match = HintTagPattern().Match(sql);
        if (!match.Success) return;

        // Remove the tag comment
        sql = HintTagPattern().Replace(sql, string.Empty);

        // Inject the hint after the first SELECT keyword
        var hint = $"/*+ {match.Groups[1].Value} */ ";
        var selectIdx = sql.IndexOf("SELECT", StringComparison.OrdinalIgnoreCase);
        if (selectIdx >= 0)
        {
            var insertAt = selectIdx + "SELECT".Length;
            sql = sql.Insert(insertAt, " " + hint);
        }

        command.CommandText = sql;
    }
}
