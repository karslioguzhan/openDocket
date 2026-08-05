import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { logout } from "../api";
import { useAuth } from "../auth";
import { LanguageSwitcher } from "./LanguageSwitcher";

export function Layout() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleLogout = async () => {
    await logout();
    await refresh();
    navigate("/login");
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">📋 openDocket</div>
        <nav>
          <NavLink to="/" end>
            {t("nav.dashboard")}
          </NavLink>
          <NavLink to="/contracts">{t("nav.contracts")}</NavLink>
          <NavLink to="/counterparties">{t("nav.counterparties")}</NavLink>
          <NavLink to="/settings">{t("nav.settings")}</NavLink>
          <NavLink to="/trash">{t("nav.trash")}</NavLink>
          {user?.is_superuser && <NavLink to="/admin">{t("nav.admin")}</NavLink>}
        </nav>
        <div className="userbox">
          <div>
            {user?.display_name ?? user?.email}
            {user?.is_superuser && ` · ${t("nav.adminSuffix")}`}
          </div>
          <div style={{ marginTop: 12 }}>
            <LanguageSwitcher />
          </div>
          <button className="btn secondary" style={{ marginTop: 8 }} onClick={handleLogout}>
            {t("nav.signOut")}
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
