import { useTranslation } from "react-i18next";

const LANGS = [
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
  { code: "tr", label: "Türkçe" },
] as const;

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  return (
    <select
      className="lang-switch"
      value={i18n.language}
      aria-label="Language"
      onChange={(e) => i18n.changeLanguage(e.target.value)}
    >
      {LANGS.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}
