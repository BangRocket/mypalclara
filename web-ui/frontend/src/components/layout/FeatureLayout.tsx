import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Sun, Moon, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/auth/AuthProvider";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";

interface FeatureLayoutProps {
  title: string;
  children: ReactNode;
}

export function FeatureLayout({ title, children }: FeatureLayoutProps) {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-border px-4 py-2">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/">
            <ArrowLeft size={18} />
          </Link>
        </Button>
        <h1 className="text-sm font-semibold">{title}</h1>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Theme toggle */}
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </Button>

        {/* User */}
        {user && (
          <div className="flex items-center gap-2">
            <Avatar className="h-6 w-6">
              <AvatarImage src={user.avatar_url || undefined} />
              <AvatarFallback className="text-[10px]">
                {user.display_name?.[0]?.toUpperCase() || "?"}
              </AvatarFallback>
            </Avatar>
            <Button variant="ghost" size="icon" onClick={logout} title="Log out">
              <LogOut size={14} />
            </Button>
          </div>
        )}
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
