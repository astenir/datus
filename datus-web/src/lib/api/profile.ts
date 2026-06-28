import { get } from "@/lib/request";
import type {
  ApiResponse,
  MeSessionsData,
  MeSummary,
  MeUsage,
} from "@/types/profile";

export const meApi = {
  summary(): Promise<ApiResponse<MeSummary>> {
    return get<ApiResponse<MeSummary>>("/api/v1/me");
  },

  permissions(): Promise<ApiResponse<string[]>> {
    return get<ApiResponse<string[]>>("/api/v1/me/permissions");
  },

  datasourceGrants(): Promise<ApiResponse<Record<string, unknown>>> {
    return get<ApiResponse<Record<string, unknown>>>("/api/v1/me/datasource-grants");
  },

  features(): Promise<ApiResponse<Record<string, boolean>>> {
    return get<ApiResponse<Record<string, boolean>>>("/api/v1/me/features");
  },

  sessions(): Promise<ApiResponse<MeSessionsData>> {
    return get<ApiResponse<MeSessionsData>>("/api/v1/me/sessions");
  },

  usage(): Promise<ApiResponse<MeUsage[]>> {
    return get<ApiResponse<MeUsage[]>>("/api/v1/me/usage");
  },
};
