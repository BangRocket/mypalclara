import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { Brain, MessageCircle, Network, Zap, Settings, LogOut, Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/auth/AuthProvider";
import { admin } from "@/api/client";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const NAV_ITEMS = [
  { to: "/", icon: Brain, label: "Knowledge Base" },
  { to: "/chat", icon: MessageCircle, label: "Chat" },
  { to: "/graph", icon: Network, label: "Graph Explorer" },
  { to: "/intentions", icon: Zap, label: "Intentions" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    if (user?.is_admin) {
      admin.pendingCount().then((res) => setPendingCount(res.count)).catch(() => {});
    }
  }, [user?.is_admin]);

  return (
    <aside className="w-60 bg-card border-r border-border flex flex-col h-screen shrink-0">
      {/* Logo */}
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-bold text-primary">Clara</h1>
        <p className="text-xs text-muted-foreground mt-0.5">Knowledge & Memory</p>
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
                  ? "bg-primary/15 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}

        {/* Admin link */}
        {user?.is_admin && (
          <NavLink
            to="/admin/users"
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition mt-2",
                isActive
                  ? "bg-primary/15 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <Shield size={18} />
            <span className="flex-1">Admin</span>
            {pendingCount > 0 && (
              <Badge variant="default" className="bg-amber-500 hover:bg-amber-500 text-white text-[10px] h-[18px] min-w-[18px] px-1">
                {pendingCount}
              </Badge>
            )}
          </NavLink>
        )}
      </nav>

      {/* User */}
      {user && (
        <div className="p-3 border-t border-border flex items-center gap-2">
          <Avatar className="w-8 h-8">
            <AvatarImage src={user.avatar_url || undefined} alt={user.display_name} />
            <AvatarFallback className="bg-primary/20 text-primary text-xs">
              {user.display_name?.[0]?.toUpperCase() || "?"}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user.display_name}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={logout} title="Sign out" className="h-8 w-8">
            <LogOut size={16} />
          </Button>
        </div>
      )}
    </aside>
  );
}
