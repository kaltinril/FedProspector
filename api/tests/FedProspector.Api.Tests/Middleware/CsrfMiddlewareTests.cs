using System.Text.Json;
using FedProspector.Api.Middleware;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Moq;

namespace FedProspector.Api.Tests.Middleware;

public class CsrfMiddlewareTests
{
    private readonly Mock<ILogger<CsrfMiddleware>> _loggerMock = new();

    private CsrfMiddleware CreateMiddleware(RequestDelegate next)
    {
        return new CsrfMiddleware(next, _loggerMock.Object);
    }

    private static DefaultHttpContext CreateHttpContext()
    {
        var context = new DefaultHttpContext();
        context.Response.Body = new MemoryStream();
        return context;
    }

    private static async Task<JsonDocument?> ReadResponseBody(HttpContext context)
    {
        context.Response.Body.Seek(0, SeekOrigin.Begin);
        return await JsonSerializer.DeserializeAsync<JsonDocument>(context.Response.Body);
    }

    // --- GET requests skip CSRF ---

    [Fact]
    public async Task InvokeAsync_GetRequest_SkipsCsrfValidation()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "GET";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue("GET requests should skip CSRF validation");
    }

    [Fact]
    public async Task InvokeAsync_GetRequest_NoCookiesNeeded()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "GET";
        // No cookies or headers set at all

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue();
        context.Response.StatusCode.Should().NotBe(403);
    }

    // --- Bearer auth skips CSRF ---

    [Fact]
    public async Task InvokeAsync_PostWithBearerToken_SkipsCsrfValidation()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "POST";
        context.Request.Headers.Authorization = "Bearer some-jwt-token";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue("Bearer auth should skip CSRF check");
    }

    [Fact]
    public async Task InvokeAsync_PatchWithBearerToken_SkipsCsrfValidation()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "PATCH";
        context.Request.Headers.Authorization = "Bearer jwt-token-value";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue();
    }

    [Fact]
    public async Task InvokeAsync_DeleteWithBearerToken_SkipsCsrfValidation()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "DELETE";
        context.Request.Headers.Authorization = "Bearer jwt-token-value";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue();
    }

    // --- Cookie auth with valid CSRF token ---

    [Fact]
    public async Task InvokeAsync_PostWithCookieAuthAndMatchingCsrfToken_Succeeds()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "POST";
        context.Request.Headers.Cookie = "access_token=jwt-value; XSRF-TOKEN=csrf-token-123";
        context.Request.Headers["X-XSRF-TOKEN"] = "csrf-token-123";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue("matching CSRF tokens should allow the request");
    }

    // --- Cookie auth WITHOUT CSRF token ---

    [Fact]
    public async Task InvokeAsync_PostWithCookieAuthAndNoCsrfHeader_Returns403()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "POST";
        context.Request.Headers.Cookie = "access_token=jwt-value; XSRF-TOKEN=csrf-token-123";
        // No X-XSRF-TOKEN header

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeFalse("request should be blocked");
        context.Response.StatusCode.Should().Be(403);
    }

    [Fact]
    public async Task InvokeAsync_PostWithCookieAuthAndMismatchedCsrfToken_Returns403()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "POST";
        context.Request.Headers.Cookie = "access_token=jwt-value; XSRF-TOKEN=csrf-token-123";
        context.Request.Headers["X-XSRF-TOKEN"] = "different-csrf-token";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeFalse("mismatched CSRF tokens should block the request");
        context.Response.StatusCode.Should().Be(403);
    }

    [Fact]
    public async Task InvokeAsync_PostWithCookieAuthAndNoCsrfCookie_Returns403()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "POST";
        context.Request.Headers.Cookie = "access_token=jwt-value";
        context.Request.Headers["X-XSRF-TOKEN"] = "some-token";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeFalse();
        context.Response.StatusCode.Should().Be(403);
    }

    [Fact]
    public async Task InvokeAsync_CsrfFailure_ReturnsJsonBody()
    {
        var middleware = CreateMiddleware(_ => Task.CompletedTask);
        var context = CreateHttpContext();
        context.Request.Method = "POST";
        context.Request.Headers.Cookie = "access_token=jwt-value; XSRF-TOKEN=abc";
        // No X-XSRF-TOKEN header

        await middleware.InvokeAsync(context);

        context.Response.ContentType.Should().StartWith("application/json");
        var body = await ReadResponseBody(context);
        body!.RootElement.GetProperty("statusCode").GetInt32().Should().Be(403);
        body!.RootElement.GetProperty("message").GetString().Should().Be("CSRF validation failed.");
    }

    // --- No cookie auth (no access_token cookie) ---

    [Fact]
    public async Task InvokeAsync_PostWithNoCookieAuth_SkipsCsrfValidation()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "POST";
        // No access_token cookie and no Bearer header

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue("non-cookie non-bearer requests should pass through");
    }

    // --- DELETE with cookie auth ---

    [Fact]
    public async Task InvokeAsync_DeleteWithCookieAuthAndNoCsrfToken_Returns403()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "DELETE";
        context.Request.Headers.Cookie = "access_token=jwt-value; XSRF-TOKEN=csrf-token-abc";
        // No X-XSRF-TOKEN header

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeFalse();
        context.Response.StatusCode.Should().Be(403);
    }

    [Fact]
    public async Task InvokeAsync_DeleteWithCookieAuthAndMatchingCsrfToken_Succeeds()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "DELETE";
        context.Request.Headers.Cookie = "access_token=jwt-value; XSRF-TOKEN=valid-token";
        context.Request.Headers["X-XSRF-TOKEN"] = "valid-token";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue();
    }

    // --- PATCH with cookie auth ---

    [Fact]
    public async Task InvokeAsync_PatchWithCookieAuthAndNoCsrfToken_Returns403()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "PATCH";
        context.Request.Headers.Cookie = "access_token=jwt-value; XSRF-TOKEN=csrf-token-xyz";
        // No X-XSRF-TOKEN header

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeFalse();
        context.Response.StatusCode.Should().Be(403);
    }

    // --- GenerateCsrfToken ---

    [Fact]
    public void GenerateCsrfToken_ReturnsNonEmptyString()
    {
        var token = CsrfMiddleware.GenerateCsrfToken();

        token.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public void GenerateCsrfToken_ReturnsDifferentTokensEachCall()
    {
        var token1 = CsrfMiddleware.GenerateCsrfToken();
        var token2 = CsrfMiddleware.GenerateCsrfToken();

        token1.Should().NotBe(token2, "CSRF tokens should be cryptographically random");
    }

    [Fact]
    public void GenerateCsrfToken_ReturnsBase64String()
    {
        var token = CsrfMiddleware.GenerateCsrfToken();

        // Should be valid base64
        var act = () => Convert.FromBase64String(token);
        act.Should().NotThrow("token should be a valid base64 string");
    }

    // --- CallsNextDelegate ---

    [Fact]
    public async Task InvokeAsync_NonMutatingMethod_CallsNextDelegate()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();
        context.Request.Method = "HEAD";

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue();
    }
}
