import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import {
  LLM_PRESETS,
  clearLLMConfig,
  isLLMConfigured,
  loadLLMConfig,
  presetById,
  saveLLMConfig,
} from "../llmConfig";
import type { LLMConfig, LLMTestResult } from "../types";

export function Settings() {
  const { t } = useTranslation();
  const [config, setConfig] = useState<LLMConfig>(() => {
    const saved = loadLLMConfig();
    if (saved) return saved;
    const preset = presetById("opencode");
    return { provider: preset.id, baseUrl: preset.baseUrl, model: preset.model, apiKey: "" };
  });
  const [showKey, setShowKey] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  const preset = presetById(config.provider);

  const applyPreset = (id: string) => {
    const p = presetById(id);
    setConfig((c) => ({ ...c, provider: id, baseUrl: p.baseUrl, model: p.model }));
  };

  const save = () => {
    saveLLMConfig({ ...config, apiKey: config.apiKey.trim() });
    setSavedFlash(true);
    window.setTimeout(() => setSavedFlash(false), 2000);
  };

  const test = async () => {
    setTesting(true);
    setStatus(null);
    try {
      const res = await api<LLMTestResult>("/llm/test", {
        method: "POST",
        body: JSON.stringify({
          base_url: config.baseUrl.trim(),
          api_key: config.apiKey.trim() || null,
          model: config.model.trim(),
        }),
      });
      setStatus({
        ok: res.ok,
        message: res.ok ? res.response ?? "" : res.error ?? "",
      });
    } catch (err) {
      setStatus({ ok: false, message: err instanceof Error ? err.message : String(err) });
    } finally {
      setTesting(false);
    }
  };

  const remove = () => {
    clearLLMConfig();
    const p = presetById("opencode");
    setConfig({ provider: p.id, baseUrl: p.baseUrl, model: p.model, apiKey: "" });
    setStatus(null);
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("settings.title")}</h1>
      </div>

      <form
        className="card"
        style={{ maxWidth: 640 }}
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <label>{t("settings.provider")}</label>
        <select value={config.provider} onChange={(e) => applyPreset(e.target.value)}>
          {LLM_PRESETS.map((p) => (
            <option key={p.id} value={p.id}>
              {t(p.labelKey)}
            </option>
          ))}
        </select>

        <label>{t("settings.apiKey")}</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type={showKey ? "text" : "password"}
            value={config.apiKey}
            onChange={(e) => setConfig((c) => ({ ...c, apiKey: e.target.value }))}
            placeholder={preset.needsKey ? t("settings.apiKeyPlaceholder") : t("settings.apiKeyOptional")}
            style={{ flex: 1 }}
          />
          <button type="button" className="secondary" onClick={() => setShowKey((s) => !s)}>
            {showKey ? t("settings.hideKey") : t("settings.showKey")}
          </button>
        </div>

        <label>{t("settings.baseUrl")}</label>
        <input
          value={config.baseUrl}
          onChange={(e) => setConfig((c) => ({ ...c, baseUrl: e.target.value }))}
          placeholder="https://…/v1"
        />

        <label>{t("settings.model")}</label>
        <input
          value={config.model}
          onChange={(e) => setConfig((c) => ({ ...c, model: e.target.value }))}
          placeholder="model-id"
        />

        <p className="muted" style={{ marginTop: 10 }}>
          {t("settings.hint")}
        </p>

        <div style={{ marginTop: 18, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button type="submit">{t("settings.save")}</button>
          <button
            type="button"
            className="secondary"
            onClick={test}
            disabled={testing || !config.baseUrl.trim() || !config.model.trim()}
          >
            {testing ? t("settings.testing") : t("settings.test")}
          </button>
          <button type="button" className="danger" onClick={remove}>
            {t("settings.remove")}
          </button>
          {savedFlash && <span className="muted">{t("settings.saved")}</span>}
        </div>

        {status && (
          <div className={status.ok ? "notice" : "error"} style={{ marginTop: 12 }}>
            {status.ok
              ? `${t("settings.testOk")}${status.message ? `: ${status.message}` : ""}`
              : `${t("settings.testFailed")}: ${status.message}`}
          </div>
        )}

        {isLLMConfigured(config) && (
          <p className="muted" style={{ marginTop: 10 }}>
            {t("settings.status", { model: config.model })}
          </p>
        )}
      </form>
    </>
  );
}
