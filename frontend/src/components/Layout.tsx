import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { logout } from "../api";
import { useAuth } from "../auth";

export function Layout() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();

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
            Dashboard
          </NavLink>
          <NavLink to="/contracts">Contracts</NavLink>
          <NavLink to="/counterparties">Counterparties</NavLink>
          <NavLink to="/trash">Trash</NavLink>
          {user?.is_superuser && <NavLink to="/admin">Admin</NavLink>}
        </nav>
        <div className="userbox">
          <div>
            {user?.display_name ?? user?.email}
            {user?.is_superuser && " · admin"}
          </div>
          <button className="btn secondary" style={{ marginTop: 8 }} onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
