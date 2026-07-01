import { ref } from "vue";

type InjectedConfig = {
  requestOrigin: string;
  userName: string;
};

const injectedConfig = ref<InjectedConfig>({
  requestOrigin: "",
  userName: "User",
});

export function setInjectedConfig(config: Partial<InjectedConfig>) {
  injectedConfig.value = {
    requestOrigin: config.requestOrigin ?? "",
    userName: config.userName ?? "User",
  };
}

export function getInjectedUserName(): string {
  return injectedConfig.value.userName;
}

export function getInjectedApiOrigin(): string {
  return injectedConfig.value.requestOrigin;
}
