import { shallowRef } from "vue";
import { setCurrentAccessToken, setCurrentUser, request } from "@/lib/request";
import { usePermission } from "@/composables/usePermission";

// 权限
const { fetchPermissions } = usePermission();

/**
 * 用户信息接口
 */
export interface UserInfo {
  userId: number;
  username: string;
  realname: string;
  email: string;
  mobilePhone?: string;
  fixedPhone?: string;
  company?: string;
  department?: string;
  title?: string;
  userStatus?: string;
  sortNumber?: string;
  permissionList?: (string | null)[];
}

/**
 * 认证状态
 */
export interface AuthState {
  loading: boolean;
  authenticated: boolean;
  user: UserInfo | null;
}

const state = shallowRef<AuthState>({
  loading: true,
  authenticated: false,
  user: null,
});
let checkAuthPromise: Promise<void> | null = null;

// 认证配置从环境变量获取
const AUTH_API_URL = import.meta.env.VITE_AUTH_API_URL || "";
const AUTH_LOGIN_URL = import.meta.env.VITE_AUTH_LOGIN_URL || "";
const DEV_ACCESS_TOKEN = import.meta.env.VITE_DEV_ACCESS_TOKEN || "";
const DEV_USER = import.meta.env.VITE_DEV_USER || "";

const FALLBACK_DEV_USER: UserInfo = {
  userId: 1,
  username: "admin",
  realname: "系统管理员",
  email: "",
};

export function createDevUser(rawUser: string = ""): UserInfo {
  const value = rawUser.trim();
  if (!value) {
    return FALLBACK_DEV_USER;
  }

  if (value.startsWith("{")) {
    try {
      const parsed = JSON.parse(value) as Partial<UserInfo>;
      if (parsed.username) {
        return {
          userId: parsed.userId ?? FALLBACK_DEV_USER.userId,
          username: parsed.username,
          realname: parsed.realname ?? parsed.username,
          email: parsed.email ?? "",
          mobilePhone: parsed.mobilePhone,
          fixedPhone: parsed.fixedPhone,
          company: parsed.company,
          department: parsed.department,
          title: parsed.title,
          userStatus: parsed.userStatus,
          sortNumber: parsed.sortNumber,
          permissionList: parsed.permissionList,
        };
      }
    } catch (error) {
      console.warn("VITE_DEV_USER JSON 解析失败，按用户名处理:", error);
    }
  }

  return {
    userId: FALLBACK_DEV_USER.userId,
    username: value,
    realname: value,
    email: "",
  };
}

const DEV_DEFAULT_USER = createDevUser(DEV_USER);

/**
 * 判断是否为本地开发环境
 * VITE_DEV_USER 用于本地直接指定用户，避免额外 mock 用户中心。
 * 未指定 VITE_DEV_USER 且无 VITE_DEV_ACCESS_TOKEN 时，保持原有 admin 开发用户。
 */
function isLocalDevelopment(): boolean {
  return import.meta.env.DEV && (!!DEV_USER || !!DEV_ACCESS_TOKEN || !AUTH_API_URL);
}

/**
 * 从 cookie 中获取 access_token
 */
function getAccessTokenFromCookie(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split("=");
    if (name === "access_token") {
      return decodeURIComponent(value);
    }
  }
  return null;
}

/**
 * 获取 access_token
 * 优先使用环境变量中的测试 token（开发环境），其次使用 cookie 中的 token
 */
function getAccessToken(): string | null {
  // 优先使用环境变量中的测试 token
  if (DEV_ACCESS_TOKEN) {
    return DEV_ACCESS_TOKEN;
  }
  // 其次使用 cookie 中的 token
  return getAccessTokenFromCookie();
}

/**
 * 清除 cookie 中的 access_token
 */
function clearAccessTokenCookie(): void {
  // 设置过期时间为过去时间，浏览器会自动删除
  document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
}

/**
 * 跳转到登录页
 */
function redirectToLogin(): void {
  if (AUTH_LOGIN_URL) {
    location.href = AUTH_LOGIN_URL;
  }
}

function clearAuthState(): void {
  setCurrentAccessToken(null);
  setCurrentUser(null);
  state.value = { loading: false, authenticated: false, user: null };
}

/**
 * 获取用户详情
 */
async function fetchUserInfo(token: string): Promise<UserInfo> {
  const response = await request(AUTH_API_URL, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });
  return response.json();
}

async function activateAuthenticatedUser(user: UserInfo, token: string | null): Promise<void> {
  setCurrentAccessToken(token);
  setCurrentUser(user);

  const permissions = await fetchPermissions();
  if (!permissions) {
    clearAuthState();
    redirectToLogin();
    return;
  }

  state.value = {
    loading: false,
    authenticated: true,
    user,
  };
}

/**
 * 认证 composable
 * 处理登录校验、用户信息获取等逻辑
 */
export function useAuth() {
  /**
   * 执行认证校验
   */
  async function checkAuth(): Promise<void> {
    if (checkAuthPromise) {
      return checkAuthPromise;
    }

    checkAuthPromise = runCheckAuth();
    try {
      await checkAuthPromise;
    } finally {
      checkAuthPromise = null;
    }
  }

  async function runCheckAuth(): Promise<void> {
    state.value = { ...state.value, loading: true };

    // 本地开发环境，免鉴权，使用默认用户数据
    if (isLocalDevelopment()) {
      await activateAuthenticatedUser(DEV_DEFAULT_USER, getAccessToken());
      return;
    }

    try {
      // 获取 access_token（优先环境变量，其次 cookie）
      const token = getAccessToken();

      if (!token) {
        // token 为空，跳转登录页
        clearAuthState();
        redirectToLogin();
        return;
      }

      // 调用用户详情接口
      const result = await fetchUserInfo(token);

      // 判断是否认证成功：code 为 200 且 data 不为空
      if (result && Object.keys(result)?.length) {
        await activateAuthenticatedUser(result, token);
      } else {
        // 认证失败，跳转登录页
        clearAuthState();
        redirectToLogin();
      }
    } catch (error) {
      console.error("认证校验失败:", error);
      // 发生错误，跳转登录页
      clearAuthState();
      redirectToLogin();
    }
  }

  /**
   * 登出
   */
  async function logout(): Promise<void> {
    // 清除认证相关的前端缓存，保留主题、API 地址等本地偏好。
    sessionStorage.removeItem("datus_permission_cache");

    // 清除 cookie 中的 access_token
    clearAccessTokenCookie();

    // 重置状态
    clearAuthState();

    // 判断是否本地开发模式
    const isDev = import.meta.env.DEV && !DEV_ACCESS_TOKEN;

    if (!isDev) {
      // 非开发模式：跳转到登录页
      redirectToLogin();
    } else {
      // 本地开发模式：刷新页面
      location.reload();
    }
  }

  return {
    state,
    checkAuth,
    logout,
  };
}
