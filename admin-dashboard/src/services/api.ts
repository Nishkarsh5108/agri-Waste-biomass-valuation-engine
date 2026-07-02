const API_BASE = "https://agri-waste-biomass-valuation-engine.onrender.com";

export const apiCall = async (endpoint: string, options: RequestInit = {}) => {
  const token = localStorage.getItem("jwt_token");
  
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("jwt_token");
      window.location.href = "/login";
    }
    const errorData = await response.json().catch(() => ({}));
    let errorMessage = "API request failed";
    if (typeof errorData.detail === 'string') {
        errorMessage = errorData.detail;
    } else if (Array.isArray(errorData.detail)) {
        errorMessage = errorData.detail.map((e: any) => e.msg).join(", ");
    }
    throw new Error(errorMessage);
  }

  return response.json();
};
