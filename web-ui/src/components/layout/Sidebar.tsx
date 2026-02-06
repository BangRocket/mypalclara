import { NavLink } from "react-router-dom";
import { Brain, MessageCircle, Network, Zap, Settings, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/auth/AuthProvider";

const NAV_ITEMS = [
  { to: "/", icon: Brain, label: "Knowledge Base" },
  { to: "/chat", icon: MessageCircle, label: "Chat" },
  { to: "/graph", icon: Network, label: "Graph Explorer" },
  { to: "/intentions", icon: Zap, label: "Intentions" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();

  return (
    <aside className="w-60 bg-surface-raised border-r border-border flex flex-col h-screen shrink-0">
      {/* Logo */}
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-bold text-accent">Clara</h1>
        <p className="text-xs text-text-muted mt-0.5">Knowledge & Memory</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-0.5">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition",
                isActive
                  ? "bg-accent/15 text-accent font-medium"
                  : "text-text-secondary hover:bg-surface-overlay hover:text-text-primary",
              )
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      {user && (
        <div className="p-3 border-t border-border flex items-center gap-2">
          {user.avatar_url ? (
            <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-full" />
          ) : (
            <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold text-accent">
              {user.display_name?.[0]?.toUpperCase() || "?"}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user.display_name}</p>
          </div>
          <button onClick={logout} className="text-text-muted hover:text-danger transition" title="Sign out">
            <LogOut size={16} />
          </button>
        </div>
      )}
    </aside>
  );
}
