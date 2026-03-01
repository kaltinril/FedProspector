using FedProspector.Core.DTOs;
using FedProspector.Core.Models;

namespace FedProspector.Core.Interfaces;

public interface IAuthService
{
    Task<AuthResult> LoginAsync(string email, string password);
    Task<bool> LogoutAsync(int userId, string tokenHash);
    Task<AppUser?> GetUserByIdAsync(int userId);
    string HashPassword(string password);
    bool VerifyPassword(string password, string hashedPassword);
}
