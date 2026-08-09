import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { demoLogin, login } from "../api";
import { useAuth } from "../auth";
import { LanguageSwitcher } from "../components/LanguageSwitcher";

export function Login() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { refresh } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      await refresh();
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("login.failed"));
    } finally {
      setBusy(false);
    }
  };

  const demo = async () => {
    setError(null);
    setBusy(true);
    try {
      await demoLogin();
      await refresh();
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("login.demoFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-box" onSubmit={submit}>
        <h1>📋 openDocket</h1>
        <div style={{ textAlign: "right", marginBottom: 8 }}>
          <LanguageSwitcher />
        </div>
        {error && <div className="error">{error}</div>}
        <label>{t("login.email")}</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
          required
        />
        <label>{t("login.password")}</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        <div style={{ marginTop: 20 }}>
          <button type="submit" disabled={busy}>
            {busy ? t("login.signingIn") : t("login.signIn")}
          </button>
        </div>
        <div className="login-demo">
          <div className="login-demo-divider">{t("login.demoOr")}</div>
          <button type="button" className="btn secondary" onClick={demo} disabled={busy}>
            {t("login.demo")}
          </button>
          <p className="muted login-demo-hint">{t("login.demoHint")}</p>
        </div>
      </form>
    </div>
  );
}
