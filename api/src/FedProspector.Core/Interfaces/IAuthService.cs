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
    Task<AuthResult> RegisterAsync(RegisterRequest request, bool isAdminRegistration = false);
    Task ChangePasswordAsync(int userId, string currentPassword, string newPassword);
    Task<UserProfileDto> GetProfileAsync(int userId);
    Task<UserProfileDto> UpdateProfileAsync(int userId, UpdateProfileRequest request);
}
