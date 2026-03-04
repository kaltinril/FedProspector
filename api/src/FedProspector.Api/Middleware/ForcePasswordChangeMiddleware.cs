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
                var isAllowed = (path.EndsWith("/auth/change-password") && method == "POST") ||
                                (path.EndsWith("/auth/logout") && method == "POST") ||
                                (path.EndsWith("/auth/me") && method == "GET");

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
