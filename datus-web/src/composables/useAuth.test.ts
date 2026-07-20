import { afterEach, describe, expect, it, vi } from "vitest";

const toastError = vi.hoisted(() => vi.fn());

vi.mock("vue-sonner", () => ({
  toast: { error: toastError },
}));

import { getCurrentAccessToken, getCurrentUser, setCurrentAccessToken, setCurrentUser } from "@/lib/request";
import { usePermission } from "./usePermission";
import {
  buildAuthLoginUrl,
  consumePostLoginRedirect,
  createDevUser,
  rememberPostLoginRedirect,
  useAuth,
} from "./useAuth";

function mockJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    statusText: status === 200 ? "OK" : "Service Unavailable",
    headers: { "Content-Type": "application/json" },
  });
}

function stubAccessTokenCookie(token: string): void {
  vi.stubGlobal("document", {
    cookie: `access_token=${encodeURIComponent(token)}`,
  });
}

describe("useAuth", () => {
  afterEach(() => {
    const auth = useAuth();
    auth.state.value = { loading: true, authenticated: false, user: null };
    auth.failureMessage.value = null;
    usePermission().clearPermissions();
    setCurrentAccessToken(null);
    setCurrentUser(null);
    toastError.mockReset();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shares auth state across consumers", () => {
    const first = useAuth();
    const second = useAuth();

    expect(first.state).toBe(second.state);
  });

  it("stores and consumes the post-login chat redirect marker once", () => {
    const storage = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem: vi.fn((key: string) => storage.delete(key)),
    });

    rememberPostLoginRedirect();

    expect(consumePostLoginRedirect()).toBe(true);
    expect(consumePostLoginRedirect()).toBe(false);
  });

  it("adds the chat targetUrl to the external login URL", () => {
    const loginUrl = buildAuthLoginUrl(
      "http://passport.dev.phfund.com.cn:8008/casLogin/login.html",
      "http://datus.example.com/datus/chat",
    );

    expect(loginUrl).toBe(
      "http://passport.dev.phfund.com.cn:8008/casLogin/login.html?targetUrl=http%3A%2F%2Fdatus.example.com%2Fdatus%2Fchat",
    );
  });

  it("replaces an existing login targetUrl", () => {
    const loginUrl = buildAuthLoginUrl(
      "https://passport.example.com/index?targetUrl=https%3A%2F%2Fold.example.com&source=datus",
      "https://datus.example.com/chat",
    );

    expect(loginUrl).toBe(
      "https://passport.example.com/index?targetUrl=https%3A%2F%2Fdatus.example.com%2Fchat&source=datus",
    );
  });

  it("creates a named dev user from VITE_DEV_USER", () => {
    expect(createDevUser("alice")).toMatchObject({
      userId: 1,
      username: "alice",
      realname: "alice",
      email: "",
    });
  });

  it("creates a dev user from JSON", () => {
    expect(createDevUser('{"userId":2,"username":"alice","realname":"Alice","department":"research"}')).toMatchObject({
      userId: 2,
      username: "alice",
      realname: "Alice",
      department: "research",
    });
  });

  it("marks local dev auth ready only after permissions load", async () => {
    stubAccessTokenCookie("dev-alice-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({
      success: true,
      data: {
        user_id: "admin",
        is_admin: true,
        permissions: ["feature:admin"],
        features: { admin: true },
        datasource_grants: {},
      },
    }));

    const auth = useAuth();
    await auth.checkAuth();

    expect(auth.state.value).toMatchObject({
      loading: false,
      authenticated: true,
      user: { username: "admin" },
    });
    expect(getCurrentUser()?.username).toBe("admin");
    expect(getCurrentAccessToken()).toBe("dev-alice-token");
  });

  it("coalesces concurrent auth checks into one permission summary request", async () => {
    stubAccessTokenCookie("dev-alice-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({
      success: true,
      data: {
        user_id: "admin",
        is_admin: true,
        permissions: ["feature:admin"],
        features: { admin: true },
        datasource_grants: {},
      },
    }));

    const auth = useAuth();
    await Promise.all([auth.checkAuth(), auth.checkAuth()]);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(auth.state.value.authenticated).toBe(true);
  });

  it("clears local dev auth when the protected permission summary fails", async () => {
    stubAccessTokenCookie("dev-alice-token");
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse(
      { success: false, errorMessage: "backend unavailable" },
      503,
    ));
    setCurrentAccessToken("stale-token");
    setCurrentUser(createDevUser("stale-user"));

    const auth = useAuth();
    await auth.checkAuth();

    expect(auth.state.value).toEqual({
      loading: false,
      authenticated: false,
      user: null,
    });
    expect(auth.failureMessage.value).toBe("认证服务暂时不可用，请稍后重新验证。");
    expect(getCurrentUser()).toBeNull();
    expect(getCurrentAccessToken()).toBeNull();
    expect(toastError).not.toHaveBeenCalled();
  });

  it("handles repeated Datus 401 responses as one friendly expired-login flow", async () => {
    stubAccessTokenCookie("expired-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse(
      { detail: "AUTH_TOKEN_INVALID" },
      401,
    ));
    setCurrentAccessToken("expired-token");
    setCurrentUser(createDevUser("alice"));

    const auth = useAuth();
    auth.state.value = {
      loading: false,
      authenticated: true,
      user: createDevUser("alice"),
    };

    await usePermission().fetchPermissions();
    await usePermission().fetchPermissions();

    expect(auth.state.value).toEqual({
      loading: false,
      authenticated: false,
      user: null,
    });
    expect(auth.failureMessage.value).toBe("登录状态已过期，请重新登录后再继续操作。");
    expect(getCurrentUser()).toBeNull();
    expect(getCurrentAccessToken()).toBeNull();
    expect(document.cookie).toContain("access_token=;");
    expect(toastError).toHaveBeenCalledTimes(1);
    expect(toastError).toHaveBeenCalledWith("登录已过期", expect.objectContaining({
      description: expect.stringContaining("重新登录"),
    }));
  });

  it("logs out without clearing non-auth local storage", async () => {
    const removeSessionItem = vi.fn();
    const clearLocalStorage = vi.fn();
    const reload = vi.fn();

    vi.stubGlobal("sessionStorage", {
      removeItem: removeSessionItem,
    });
    vi.stubGlobal("localStorage", {
      clear: clearLocalStorage,
    });
    vi.stubGlobal("document", {
      cookie: "access_token=dev-alice-token",
    });
    vi.stubGlobal("location", {
      href: "",
      reload,
    });
    setCurrentAccessToken("dev-alice-token");
    setCurrentUser(createDevUser("alice"));

    const auth = useAuth();
    auth.state.value = {
      loading: false,
      authenticated: true,
      user: createDevUser("alice"),
    };

    await auth.logout();

    expect(removeSessionItem).toHaveBeenCalledWith("datus_permission_cache");
    expect(clearLocalStorage).not.toHaveBeenCalled();
    expect(getCurrentUser()).toBeNull();
    expect(getCurrentAccessToken()).toBeNull();
    expect(auth.state.value.authenticated).toBe(false);
    expect(reload).toHaveBeenCalled();
  });
});
