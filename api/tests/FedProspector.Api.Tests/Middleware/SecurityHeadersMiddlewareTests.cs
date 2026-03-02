using FedProspector.Api.Middleware;
using FluentAssertions;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Moq;

namespace FedProspector.Api.Tests.Middleware;

public class SecurityHeadersMiddlewareTests
{
    private static DefaultHttpContext CreateHttpContext(bool isDevelopment)
    {
        var envMock = new Mock<IWebHostEnvironment>();
        envMock.Setup(e => e.EnvironmentName)
               .Returns(isDevelopment ? "Development" : "Production");

        var services = new ServiceCollection();
        services.AddSingleton(envMock.Object);

        var context = new DefaultHttpContext
        {
            RequestServices = services.BuildServiceProvider()
        };
        return context;
    }

    private static SecurityHeadersMiddleware CreateMiddleware(RequestDelegate? next = null)
    {
        next ??= _ => Task.CompletedTask;
        return new SecurityHeadersMiddleware(next);
    }

    [Fact]
    public async Task InvokeAsync_SetsXContentTypeOptionsHeader()
    {
        var middleware = CreateMiddleware();
        var context = CreateHttpContext(isDevelopment: true);

        await middleware.InvokeAsync(context);

        context.Response.Headers["X-Content-Type-Options"].ToString().Should().Be("nosniff");
    }

    [Fact]
    public async Task InvokeAsync_SetsXFrameOptionsHeader()
    {
        var middleware = CreateMiddleware();
        var context = CreateHttpContext(isDevelopment: true);

        await middleware.InvokeAsync(context);

        context.Response.Headers["X-Frame-Options"].ToString().Should().Be("DENY");
    }

    [Fact]
    public async Task InvokeAsync_SetsApiVersionHeader()
    {
        var middleware = CreateMiddleware();
        var context = CreateHttpContext(isDevelopment: true);

        await middleware.InvokeAsync(context);

        context.Response.Headers["X-Api-Version"].ToString().Should().Be("1.0");
    }

    [Fact]
    public async Task InvokeAsync_RemovesServerHeader()
    {
        var middleware = CreateMiddleware();
        var context = CreateHttpContext(isDevelopment: true);
        context.Response.Headers["Server"] = "Kestrel";

        await middleware.InvokeAsync(context);

        context.Response.Headers.ContainsKey("Server").Should().BeFalse();
    }

    [Fact]
    public async Task InvokeAsync_Production_SetsHstsHeader()
    {
        var middleware = CreateMiddleware();
        var context = CreateHttpContext(isDevelopment: false);

        await middleware.InvokeAsync(context);

        context.Response.Headers["Strict-Transport-Security"].ToString()
            .Should().Be("max-age=31536000; includeSubDomains");
    }

    [Fact]
    public async Task InvokeAsync_Development_DoesNotSetHstsHeader()
    {
        var middleware = CreateMiddleware();
        var context = CreateHttpContext(isDevelopment: true);

        await middleware.InvokeAsync(context);

        context.Response.Headers.ContainsKey("Strict-Transport-Security").Should().BeFalse();
    }

    [Fact]
    public async Task InvokeAsync_CallsNextDelegate()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext(isDevelopment: true);

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue();
    }
}
