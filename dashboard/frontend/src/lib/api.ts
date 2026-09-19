import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// In-memory access token (never persisted to localStorage)
let _accessToken: string | null = null;

export function setAccessToken(t: string | null) {
  _accessToken = t;
}
export function getAccessToken() {
  return _accessToken;
}

export const api = axios.create({ baseURL: BASE, withCredentials: true });

// Attach bearer token to every request
api.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`;
  }
  return config;
});

// On 401, try to silently refresh
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        // Refresh token is stored in cookie by the browser, so we just call refresh.
        // If it fails, the cookie is expired/missing.
        const { data } = await axios.post(`${BASE}/auth/refresh`, {}, { withCredentials: true });
        setAccessToken(data.access_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch {
        setAccessToken(null);
        localStorage.removeItem("has_session");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// --- Auth ---
export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>("/auth/login", {
      email,
      password,
    }),
  refresh: () =>
    api.post<{ access_token: string }>("/auth/refresh"),
  logout: () =>
    api.post("/auth/logout"),
  me: () => api.get("/auth/me"),

  register: (email: string, password: string) =>
    api.post<{ detail: string }>("/auth/register", { email, password }),

  forgotPassword: (email: string) =>
    api.post<{ detail: string }>("/auth/forgot-password", { email }),

  resetPassword: (email: string, code: string, new_password: string) =>
    api.post<{ detail: string }>("/auth/reset-password", {
      email,
      code,
      new_password,
    }),
};


// --- Analytics ---
export const analyticsApi = {
  overview: () => api.get("/analytics/overview"),
};

// --- Competitors ---
export const competitorsApi = {
  list: () => api.get("/competitors"),
  get: (id: number) => api.get(`/competitors/${id}`),
  pages: (id: number, page = 1, pageSize = 50) =>
    api.get(`/competitors/${id}/pages`, { params: { page, page_size: pageSize } }),
  products: (id: number, page = 1, pageSize = 50) =>
    api.get(`/competitors/${id}/products`, { params: { page, page_size: pageSize } }),
};

// --- SEO ---
export const seoApi = {
  summary: () => api.get("/seo/summary"),
  gapMatrix: () => api.get("/seo/gap-matrix"),
  actionPlan: (id: number) => api.get(`/seo/action-plan/${id}`),
  topIssues: (id: number, limit = 20) =>
    api.get(`/seo/top-issues/${id}`, { params: { limit } }),
};

// --- Performance ---
export const performanceApi = {
  summary: () => api.get("/performance/summary"),
  pages: (id: number, page = 1) =>
    api.get(`/performance/pages/${id}`, { params: { page } }),
  speedBreakdown: (id: number) => api.get(`/performance/speed-breakdown/${id}`),
};

// --- Social ---
export const socialApi = {
  summary: () => api.get("/social/summary"),
  timeSeries: (id: number, platform?: string) =>
    api.get(`/social/time-series/${id}`, { params: platform ? { platform } : {} }),
  forecast: (id: number) => api.get(`/social/forecast/${id}`),
  posts: (id: number, platform?: string, limit = 20) =>
    api.get(`/social/posts/${id}`, { params: { limit, ...(platform ? { platform } : {}) } }),
  accounts: (id: number) => api.get(`/social/accounts/${id}`),
  aiAnalysis: (id: number, platform?: string) =>
    api.get(`/social/ai-analysis/${id}`, { params: platform ? { platform } : {} }),
};

// --- Market ---
export const marketApi = {
  scores: () => api.get("/market/scores"),
  categories: () => api.get("/market/categories"),
  search: (q: string, competitorId?: number) =>
    api.get("/market/products/search", { params: { q, ...(competitorId ? { competitor_id: competitorId } : {}) } }),
  priceHistory: (id: number) => api.get(`/market/price-history/${id}`),
  stockHistory: (id: number) => api.get(`/market/stock-history/${id}`),
};

// --- Crawl ---
export const crawlApi = {
  jobs: (params?: Record<string, unknown>) => api.get("/crawl/jobs", { params }),
  stats: () => api.get("/crawl/stats"),
  statsAggregate: () => api.get("/crawl/stats/aggregate"),
  triggerUrl: (url: string, priority = 5) =>
    api.post("/crawl/trigger", { url, priority }),
  scraperHealth: () => api.get("/crawl/scraper-health"),
  refreshViews: () => api.post("/crawl/refresh-views"),
};

// --- Competitor Comparison ---
export const comparisonApi = {
  compare: (ids: number[]) =>
    api.get("/competitors/compare", { params: { ids: ids.join(",") } }),
};

// --- Reports ---
export const reportsApi = {
  list: () => api.get("/reports/"),
  create: (title: string, filters: any) => api.post("/reports/", { title, filters }),
  delete: (id: string) => api.delete(`/reports/${id}`),
  generate: (payload: {
    report_type: "competitor_platform" | "social_media" | "seo_gap" | "refresh_views";
    competitor_id?: number;
    title?: string;
    extra?: Record<string, unknown>;
  }) => api.post("/reports/generate", payload),
};

// --- Webhooks ---
export const webhooksApi = {
  events: (source?: string, limit = 50) =>
    api.get("/webhooks/events", { params: { source, limit } }),
};

// --- Council ---
export const councilApi = {
  createSession: (payload: {
    question: string;
    domain_profile: "general" | "social" | "market" | "seo";
    competitor_id?: number;
  }) =>
    api.post<{ session_id: string; status: string; created_at: string }>(
      "/council/sessions",
      payload
    ),

  getSession: (id: string) =>
    api.get<{
      id: string;
      user_id: string;
      question: string;
      domain_profile: string;
      competitor_id: number | null;
      status: "pending" | "running" | "completed" | "failed";
      advisor_responses: Record<string, unknown> | null;
      html_report: string | null;
      error_message: string | null;
      created_at: string;
      completed_at: string | null;
    }>(`/council/sessions/${id}`),

  listSessions: () =>
    api.get<
      Array<{
        id: string;
        question: string;
        domain_profile: string;
        competitor_id: number | null;
        status: "pending" | "running" | "completed" | "failed";
        created_at: string;
        completed_at: string | null;
      }>
    >("/council/sessions"),
};
