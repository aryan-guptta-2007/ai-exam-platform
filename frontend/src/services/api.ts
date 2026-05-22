const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface RequestOptions extends RequestInit {
  json?: any;
}

export class ApiClient {
  private static async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const url = `${BASE_URL}${path}`;
    
    // Set headers
    const headers = new Headers(options.headers || {});
    if (options.json && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
      options.body = JSON.stringify(options.json);
    }

    // Load Access Token from localStorage
    const accessToken = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    if (accessToken && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }

    options.headers = headers;

    const response = await fetch(url, options);

    if (response.status === 401 && typeof window !== "undefined") {
      // Token expired. Attempt refresh
      const refreshed = await this.handleTokenRefresh();
      if (refreshed) {
        // Retry the original request
        const newAccessToken = localStorage.getItem("access_token");
        headers.set("Authorization", `Bearer ${newAccessToken}`);
        const retryResponse = await fetch(url, options);
        return this.parseResponse<T>(retryResponse);
      } else {
        // Log out user
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
        throw new Error("Session expired. Please log in again.");
      }
    }

    return this.parseResponse<T>(response);
  }

  private static async parseResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let message = "An error occurred while fetching the data.";
      try {
        const errData = await response.json();
        message = errData.detail || message;
      } catch (_) {}
      throw new Error(message);
    }
    return response.json() as Promise<T>;
  }

  private static async handleTokenRefresh(): Promise<boolean> {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) return false;

    try {
      const response = await fetch(`${BASE_URL}/auth/refresh?refresh_token=${refreshToken}`, {
        method: "POST"
      });
      if (!response.ok) return false;

      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      return true;
    } catch (err) {
      console.error("Token refresh failed:", err);
      return false;
    }
  }

  // Auth Operations
  public static post<T>(path: string, json: any, options: RequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "POST", json });
  }

  public static get<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  public static delete<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "DELETE" });
  }
}
export default ApiClient;
