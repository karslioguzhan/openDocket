import type { LLMConfig } from "./types";

export interface LLMPreset {
  id: string;
  labelKey: string;
  baseUrl: string;
  model: string;
  needsKey: boolean;
}

export const LLM_PRESETS: LLMPreset[] = [
  {
    id: "opencode",
    labelKey: "settings.providerOpencode",
    baseUrl: "https://opencode.ai/zen/v1",
    model: "deepseek-v4-flash",
    needsKey: true,
  },
  {
    id: "opencode-go",
    labelKey: "settings.providerOpencodeGo",
    baseUrl: "https://opencode.ai/zen/go/v1",
    model: "deepseek-v4-flash",
    needsKey: true,
  },
  {
    id: "openai",
    labelKey: "settings.providerOpenAI",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    needsKey: true,
  },
  {
    id: "openrouter",
    labelKey: "settings.providerOpenRouter",
    baseUrl: "https://openrouter.ai/api/v1",
    model: "openai/gpt-4o-mini",
    needsKey: true,
  },
  {
    id: "groq",
    labelKey: "settings.providerGroq",
    baseUrl: "https://api.groq.com/openai/v1",
    model: "llama-3.3-70b-versatile",
    needsKey: true,
  },
  {
    id: "deepseek",
    labelKey: "settings.providerDeepSeek",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-chat",
    needsKey: true,
  },
  {
    id: "local",
    labelKey: "settings.providerLocal",
    baseUrl: "http://host.docker.internal:11434/v1",
    model: "llama3",
    needsKey: false,
  },
  {
    id: "custom",
    labelKey: "settings.providerCustom",
    baseUrl: "",
    model: "",
    needsKey: false,
  },
];

export function presetById(id: string): LLMPreset {
  return LLM_PRESETS.find((p) => p.id === id) ?? LLM_PRESETS[0];
}

const STORAGE_KEY = "opendocket.llm";

export function loadLLMConfig(): LLMConfig | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as LLMConfig;
    if (
      parsed &&
      typeof parsed.provider === "string" &&
      typeof parsed.baseUrl === "string" &&
      typeof parsed.apiKey === "string" &&
      typeof parsed.model === "string"
    ) {
      return parsed;
    }
  } catch {
    /* ignore corrupt storage */
  }
  return null;
}

export function saveLLMConfig(config: LLMConfig): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function clearLLMConfig(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function isLLMConfigured(config: LLMConfig | null): config is LLMConfig {
  return Boolean(config && config.baseUrl.trim() && config.model.trim());
}
