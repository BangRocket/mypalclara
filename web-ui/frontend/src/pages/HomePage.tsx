import { useAuth } from "@/auth/AuthProvider";
import { useQuery } from "@tanstack/react-query";
import { MenuTile } from "@/components/MenuTile";
import { admin } from "@/api/client";
import { useTheme } from "@/hooks/useTheme";
import { Sun, Moon, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

import chatIcon from "@/assets/icons/chat.png";
import knowledgeIcon from "@/assets/icons/knowledge.png";
import graphIcon from "@/assets/icons/graph.png";
import intentionsIcon from "@/assets/icons/intentions.png";
import gamesIcon from "@/assets/icons/games.png";
import settingsIcon from "@/assets/icons/settings.png";
import adminIcon from "@/assets/icons/admin.png";

export function HomePage() {
  const { user, logout } = useAuth();
  const isAdmin = user?.is_admin === true;
  const { theme, toggleTheme } = useTheme();

  const { data: pendingData } = useQuery({
    queryKey: ["admin", "pendingCount"],
    queryFn: () => admin.pendingCount(),
    enabled: isAdmin,
  });

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      {/* Top-right controls */}
      <div className="fixed right-4 top-4 flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </Button>
        <Button variant="ghost" size="icon" onClick={logout} title="Log out">
          <LogOut size={14} />
        </Button>
      </div>

      {/* Title */}
      <h1 className="mb-2 text-3xl font-bold text-foreground">Clara</h1>
      <p className="mb-10 text-sm text-muted-foreground">What would you like to do?</p>

      {/* Tile grid */}
      <div className="grid w-full max-w-2xl grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <MenuTile to="/chat" label="Chat" icon={chatIcon} accentColor="#22d3ee" />
        <MenuTile to="/knowledge" label="Knowledge" icon={knowledgeIcon} accentColor="#a855f7" />
        <MenuTile to="/graph" label="Graph" icon={graphIcon} accentColor="#22c55e" />
        <MenuTile to="/intentions" label="Intentions" icon={intentionsIcon} accentColor="#f97316" />
        <MenuTile to="/games" label="Games" icon={gamesIcon} accentColor="#ef4444" />
        <MenuTile to="/settings" label="Settings" icon={settingsIcon} accentColor="#9ca3af" />
        {isAdmin && (
          <MenuTile
            to="/admin/users"
            label="Admin"
            icon={adminIcon}
            accentColor="#eab308"
            badge={pendingData?.count}
          />
        )}
      </div>
    </div>
  );
}
