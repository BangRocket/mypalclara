import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
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

interface MenuItem {
  to: string;
  label: string;
  icon: string;
  accentColor: string;
  badge?: number;
}

export function HomePage() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const isAdmin = user?.is_admin === true;
  const [selectedIndex, setSelectedIndex] = useState(0);
  const carouselRef = useRef<HTMLDivElement>(null);

  const { data: pendingData } = useQuery({
    queryKey: ["admin", "pendingCount"],
    queryFn: () => admin.pendingCount(),
    enabled: isAdmin,
  });

  const items: MenuItem[] = useMemo(() => {
    const base: MenuItem[] = [
      { to: "/chat", label: "Chat", icon: chatIcon, accentColor: "#22d3ee" },
      { to: "/knowledge", label: "Knowledge", icon: knowledgeIcon, accentColor: "#a855f7" },
      { to: "/graph", label: "Graph", icon: graphIcon, accentColor: "#22c55e" },
      { to: "/intentions", label: "Intentions", icon: intentionsIcon, accentColor: "#f97316" },
      { to: "/games", label: "Games", icon: gamesIcon, accentColor: "#ef4444" },
      { to: "/settings", label: "Settings", icon: settingsIcon, accentColor: "#9ca3af" },
    ];
    if (isAdmin) {
      base.push({
        to: "/admin/users",
        label: "Admin",
        icon: adminIcon,
        accentColor: "#eab308",
        badge: pendingData?.count,
      });
    }
    return base;
  }, [isAdmin, pendingData?.count]);

  // Clamp index if items change (e.g. admin status loads)
  useEffect(() => {
    if (selectedIndex >= items.length) {
      setSelectedIndex(items.length - 1);
    }
  }, [items.length, selectedIndex]);

  const goLeft = useCallback(() => {
    setSelectedIndex((i) => (i > 0 ? i - 1 : items.length - 1));
  }, [items.length]);

  const goRight = useCallback(() => {
    setSelectedIndex((i) => (i < items.length - 1 ? i + 1 : 0));
  }, [items.length]);

  const goTo = useCallback(() => {
    const item = items[selectedIndex];
    if (item) navigate(item.to);
  }, [items, selectedIndex, navigate]);

  // Keyboard navigation
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "ArrowLeft" || e.key === "a") {
        e.preventDefault();
        goLeft();
      } else if (e.key === "ArrowRight" || e.key === "d") {
        e.preventDefault();
        goRight();
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        goTo();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goLeft, goRight, goTo]);

  const selected = items[selectedIndex];

  return (
    <div
      className="flex h-screen flex-col items-center justify-center overflow-hidden"
      style={{
        background: "linear-gradient(180deg, #0c0c14 0%, #14141f 40%, #1a1a2e 100%)",
      }}
    >
      {/* Top-right controls */}
      <div className="fixed right-4 top-4 z-10 flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          className="text-white/60 hover:text-white hover:bg-white/10"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={logout}
          title="Log out"
          className="text-white/60 hover:text-white hover:bg-white/10"
        >
          <LogOut size={14} />
        </Button>
      </div>

      {/* Title */}
      <h1 className="mb-16 text-2xl font-light tracking-widest text-white/80">
        CLARA
      </h1>

      {/* Carousel */}
      <div className="relative flex w-full items-center justify-center">
        {/* Left/right click zones */}
        <button
          onClick={goLeft}
          className="absolute left-0 z-10 flex h-full w-24 items-center justify-start pl-6 text-white/30 hover:text-white/60 transition-colors"
          aria-label="Previous"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <div
          ref={carouselRef}
          className="flex items-center justify-center gap-2"
          style={{ minHeight: 160 }}
        >
          {items.map((item, i) => {
            const offset = i - selectedIndex;
            return (
              <MenuTile
                key={item.to}
                label={item.label}
                icon={item.icon}
                accentColor={item.accentColor}
                selected={i === selectedIndex}
                offset={offset}
                badge={item.badge}
                onClick={() => {
                  if (i === selectedIndex) {
                    navigate(item.to);
                  } else {
                    setSelectedIndex(i);
                  }
                }}
              />
            );
          })}
        </div>

        <button
          onClick={goRight}
          className="absolute right-0 z-10 flex h-full w-24 items-center justify-end pr-6 text-white/30 hover:text-white/60 transition-colors"
          aria-label="Next"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 6 15 12 9 18" />
          </svg>
        </button>
      </div>

      {/* Selected item label */}
      <div className="mt-8 flex flex-col items-center gap-2">
        <p
          className="text-lg font-medium tracking-wide transition-colors duration-300"
          style={{ color: selected?.accentColor ?? "#fff" }}
        >
          {selected?.label}
        </p>
        <div
          className="h-0.5 w-12 rounded-full transition-colors duration-300"
          style={{ backgroundColor: selected?.accentColor ?? "#fff" }}
        />
      </div>

      {/* Hint */}
      <p className="mt-12 text-xs text-white/25">
        Arrow keys to browse &middot; Enter to select
      </p>
    </div>
  );
}
