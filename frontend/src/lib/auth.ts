import { apiFetch } from "./api";

interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  auth_provider: string;
  is_active: boolean;
  role: string;
  created_at: string;
}

interface AuthResponse {
  user: User;
  tokens: {
    access_token: string;
    refresh_token: string;
    token_type: string;
  };
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

function setCookie(name: string, value: string, days: number) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}

function deleteCookie(name: string) {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
}

export function saveTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem("access_token", accessToken);
  localStorage.setItem("refresh_token", refreshToken);
  setCookie("access_token", accessToken, 1);
}

export function getAccessToken(): string | null {
  return typeof window !== "undefined"
    ? localStorage.getItem("access_token")
    : null;
}

export function getRefreshToken(): string | null {
  return typeof window !== "undefined"
    ? localStorage.getItem("refresh_token")
    : null;
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  deleteCookie("access_token");
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const data = await apiFetch<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  saveTokens(data.tokens.access_token, data.tokens.refresh_token);
  return data;
}

export async function register(
  email: string,
  password: string,
  name: string,
): Promise<AuthResponse> {
  const data = await apiFetch<AuthResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });
  saveTokens(data.tokens.access_token, data.tokens.refresh_token);
  return data;
}

export async function refreshTokens(): Promise<TokenResponse> {
  const refreshToken = getRefreshToken();
  const data = await apiFetch<TokenResponse>("/api/v1/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  saveTokens(data.access_token, data.refresh_token);
  return data;
}

export async function getMe(): Promise<User> {
  return apiFetch<User>("/api/v1/auth/me");
}

export function logout() {
  clearTokens();
  window.location.href = "/login";
}

export type { User, AuthResponse, TokenResponse };
