import { NavLink, useLocation } from "react-router-dom";
import {
  Brain,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeft,
  PlusIcon,
  Sun,
  Moon,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/auth/AuthProvider";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import { useTheme } from "@/hooks/useTheme";

const NAV_ITEMS = [
  { to: "/knowledge", icon: Brain, label: "Knowledge Base" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

interface UnifiedSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
}

export function UnifiedSidebar({
  collapsed,
  onToggle,
  onNavigate,
}: UnifiedSidebarProps) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const isOnChat = location.pathname === "/";

  return (
    <aside
      className={cn(
        "flex h-full flex-col overflow-hidden border-r border-sidebar-border bg-sidebar transition-[width] duration-200",
        collapsed ? "w-0 border-r-0" : "w-72",
      )}
    >
      {/* Header: Logo + collapse */}
      <div className="flex shrink-0 items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkles size={20} className="shrink-0 text-primary" />
          <span className="text-base font-semibold text-sidebar-foreground">
            Clara
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className="h-8 w-8 text-sidebar-foreground/60 hover:text-sidebar-foreground"
          title="Collapse sidebar"
        >
          <PanelLeftClose size={18} />
        </Button>
      </div>

      {/* New Chat button */}
      <div className="shrink-0 px-3 pb-2">
        <NavLink
          to="/"
          end
          onClick={onNavigate}
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
        >
          <PlusIcon size={16} />
          New Chat
        </NavLink>
      </div>

      {/* Thread list — scrollable */}
      {isOnChat && (
        <div className="min-h-0 flex-1 overflow-y-auto px-3">
          <ThreadList />
        </div>
      )}

      {/* Spacer when not on chat */}
      {!isOnChat && <div className="flex-1" />}

      {/* Nav links */}
      <div className="shrink-0 space-y-0.5 border-t border-sidebar-border px-3 py-2">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-1.5 text-sm transition-colors",
                isActive
                  ? "bg-sidebar-accent font-medium text-sidebar-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}

      </div>

      {/* Theme toggle + User */}
      <div className="shrink-0 space-y-2 border-t border-sidebar-border px-3 py-2">
        <button
          onClick={toggleTheme}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-1.5 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>

        {user && (
          <div className="flex items-center gap-2 px-2 py-1">
            <Avatar className="h-7 w-7">
              <AvatarImage
                src={user.avatar_url || undefined}
                alt={user.display_name}
              />
              <AvatarFallback className="bg-primary/20 text-xs text-primary">
                {user.display_name?.[0]?.toUpperCase() || "?"}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-sidebar-foreground">
                {user.display_name}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              title="Sign out"
              className="h-7 w-7 text-sidebar-foreground/60 hover:text-sidebar-foreground"
            >
              <LogOut size={14} />
            </Button>
          </div>
        )}
      </div>
    </aside>
  );
}

/** Small floating button to re-open collapsed sidebar */
export function SidebarOpenButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onClick}
      className="fixed left-3 top-3 z-20 h-8 w-8 text-muted-foreground hover:text-foreground lg:left-3 lg:top-3"
      title="Open sidebar"
    >
      <PanelLeft size={18} />
    </Button>
  );
}
