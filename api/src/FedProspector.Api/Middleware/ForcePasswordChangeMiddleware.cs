using System.Text.Json;

namespace FedProspector.Api.Middleware;

public class ForcePasswordChangeMiddleware
{
    private readonly RequestDelegate _next;

    public ForcePasswordChangeMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        if (context.User.Identity?.IsAuthenticated == true)
        {
            var forceChange = context.User.FindFirst("force_password_change")?.Value;
            if (forceChange == "true")
            {
                var path = context.Request.Path.Value?.ToLowerInvariant() ?? "";
                var method = context.Request.Method;

                // Allow password change and logout only
                var isAllowed = (path.Equals("/api/v1/auth/change-password", StringComparison.OrdinalIgnoreCase) && method == "POST") ||
                                (path.Equals("/api/v1/auth/logout", StringComparison.OrdinalIgnoreCase) && method == "POST") ||
                                (path.Equals("/api/v1/auth/me", StringComparison.OrdinalIgnoreCase) && method == "GET");

                if (!isAllowed)
                {
                    context.Response.StatusCode = 403;
                    context.Response.ContentType = "application/json";
                    var response = JsonSerializer.Serialize(new { error = "Password change required" });
                    await context.Response.WriteAsync(response);
                    return;
                }
            }
        }

        await _next(context);
    }
}
