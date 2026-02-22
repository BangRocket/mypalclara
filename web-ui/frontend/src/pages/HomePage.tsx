import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { useQuery } from "@tanstack/react-query";
import { admin } from "@/api/client";
import { useTheme } from "@/hooks/useTheme";
import { Sun, Moon, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { ChromaGrid, type GridItem } from "@/components/ChromaGrid";
import Particles from "@/components/Particles";

import chatIcon from "@/assets/icons/chat.png";
import knowledgeIcon from "@/assets/icons/knowledge.png";
import graphIcon from "@/assets/icons/graph.png";
import intentionsIcon from "@/assets/icons/intentions.png";
import gamesIcon from "@/assets/icons/games.png";
import settingsIcon from "@/assets/icons/settings.png";
import adminIcon from "@/assets/icons/admin.png";
import calendarIcon from "@/assets/icons/calendar.png";
import notesIcon from "@/assets/icons/notes.png";

const DEFAULT_DETAIL =
  "Clara is your personal AI companion — she remembers your conversations, learns your preferences, and helps you stay organized.";

// Dark: vibrant neon particles
const DARK_PARTICLES = ["#4ade80", "#22d3ee", "#a855f7", "#f472b6"];
// Light: muted earthy tones — sage, warm gold, soft blush, dusty teal
const LIGHT_PARTICLES = ["#8fb5a0", "#c9a96e", "#d4a0a0", "#7eb8a8"];

export function HomePage() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const isAdmin = user?.is_admin === true;
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const light = theme === "light";

  const { data: pendingData } = useQuery({
    queryKey: ["admin", "pendingCount"],
    queryFn: () => admin.pendingCount(),
    enabled: isAdmin,
  });

  const items: GridItem[] = useMemo(() => {
    const base: GridItem[] = [
      {
        icon: chatIcon,
        label: "Chat",
        description: "Talk with Clara",
        detail: "Have a natural conversation with Clara. She remembers context from previous chats, understands your preferences, and can help with questions, brainstorming, or just keeping you company.",
        accentColor: "#22d3ee",
        onClick: () => navigate("/chat"),
      },
      {
        icon: knowledgeIcon,
        label: "Knowledge",
        description: "Memory & facts",
        detail: "Browse and manage everything Clara remembers about you — facts, preferences, and notes she's picked up from your conversations. Edit or remove anything at any time.",
        accentColor: "#a855f7",
        onClick: () => navigate("/knowledge"),
      },
      {
        icon: graphIcon,
        label: "Graph",
        description: "Relationship map",
        detail: "Explore a visual map of the people, places, and topics in your world. Clara builds this from your conversations to understand how everything connects.",
        accentColor: "#22c55e",
        onClick: () => navigate("/graph"),
      },
      {
        icon: intentionsIcon,
        label: "Intentions",
        description: "Goals & tasks",
        detail: "Set goals and track tasks with Clara's help. She can remind you about deadlines, check in on progress, and help break big goals into manageable steps.",
        accentColor: "#f97316",
        onClick: () => navigate("/intentions"),
      },
      {
        icon: gamesIcon,
        label: "Games",
        description: "Play together",
        detail: "Take a break and play games with Clara. From trivia to word games, it's a fun way to hang out when you need a change of pace.",
        accentColor: "#ef4444",
        onClick: () => navigate("/games"),
      },
      {
        icon: notesIcon,
        label: "Notes",
        description: "Write & organize",
        detail: "A personal workspace for your thoughts. Write notes, organize ideas, and let Clara help you draft, summarize, or expand on what you've written.",
        accentColor: "#ec4899",
        onClick: () => navigate("/notes"),
      },
      {
        icon: calendarIcon,
        label: "Calendar",
        description: "Events & schedule",
        detail: "Keep track of your schedule in one place. Clara can help you plan your day, set reminders, and coordinate events across your life.",
        accentColor: "#3b82f6",
        onClick: () => navigate("/calendar"),
      },
    ];
    if (isAdmin) {
      base.push({
        icon: adminIcon,
        label: "Admin",
        description: "User management",
        detail: "Manage users, review pending registrations, and configure system-wide settings. Only visible to administrators.",
        accentColor: "#eab308",
        badge: pendingData?.count,
        onClick: () => navigate("/admin/users"),
      });
    }
    // Settings always last
    base.push({
      icon: settingsIcon,
      label: "Settings",
      description: "Preferences",
      detail: "Customize how Clara works for you — adjust her personality, notification preferences, connected accounts, and other configuration options.",
      accentColor: "#9ca3af",
      onClick: () => navigate("/settings"),
    });
    return base;
  }, [isAdmin, pendingData?.count, navigate]);

  const activeItem = hoveredIndex !== null ? items[hoveredIndex] : null;
  const detailText = activeItem?.detail ?? DEFAULT_DETAIL;
  const accentRgb = activeItem
    ? hexToRgb(activeItem.accentColor)
    : light
      ? "143,181,160"
      : "135,215,160";

  return (
    <div
      className="relative flex h-screen flex-col overflow-hidden"
      style={{
        background: light
          ? "linear-gradient(180deg, #faf6ee 0%, #f5efe5 40%, #ede6d8 100%)"
          : "linear-gradient(180deg, #0c0c14 0%, #14141f 40%, #1a1a2e 100%)",
      }}
    >
      {/* Particle background */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{ opacity: light ? 0.35 : 0.7 }}
      >
        <Particles
          particleCount={300}
          particleSpread={10}
          speed={0.08}
          particleColors={light ? LIGHT_PARTICLES : DARK_PARTICLES}
          alphaParticles
          particleBaseSize={120}
          sizeRandomness={1}
          cameraDistance={20}
        />
      </div>

      {/* Header */}
      <header
        className="relative z-10 flex shrink-0 items-center gap-3 px-4 py-2"
        style={{
          borderBottom: light
            ? "1px solid rgba(160,140,110,0.15)"
            : "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div className="w-9" />
        <h1
          className="text-sm font-semibold"
          style={{ color: light ? "#6b5e50" : "rgba(255,255,255,0.7)" }}
        >
          MyPalClara
        </h1>

        <div className="flex-1" />

        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          className={
            light
              ? "text-[#8a7e70] hover:text-[#3d3529] hover:bg-black/5"
              : "text-white/60 hover:text-white hover:bg-white/10"
          }
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </Button>

        {user && (
          <div className="flex items-center gap-2">
            <Avatar className="h-6 w-6">
              <AvatarImage src={user.avatar_url || undefined} />
              <AvatarFallback className="text-[10px]">
                {user.display_name?.[0]?.toUpperCase() || "?"}
              </AvatarFallback>
            </Avatar>
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              title="Log out"
              className={
                light
                  ? "text-[#8a7e70] hover:text-[#3d3529] hover:bg-black/5"
                  : "text-white/60 hover:text-white hover:bg-white/10"
              }
            >
              <LogOut size={14} />
            </Button>
          </div>
        )}
      </header>

      {/* Main content */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center gap-4 overflow-y-auto px-4 py-8">
        <ChromaGrid
          items={items}
          onItemHover={setHoveredIndex}
          theme={theme}
        />

        {/* Description card — changes per hovered app */}
        <div
          className="relative w-full max-w-[960px] rounded-2xl p-6 transition-all duration-300"
          style={{
            border: light
              ? "1px solid rgba(160,140,110,0.12)"
              : "1px solid rgba(255,255,255,0.06)",
            background: light
              ? `linear-gradient(145deg, rgba(${accentRgb},0.08), rgba(255,255,255,0.5))`
              : `linear-gradient(145deg, rgba(${accentRgb},0.04), rgba(0,0,0,0.3))`,
          }}
        >
          <p
            className="text-base leading-relaxed transition-opacity duration-200"
            style={{ color: light ? "#6b5e50" : "rgba(255,255,255,0.5)" }}
          >
            {detailText}
          </p>
        </div>
      </main>
    </div>
  );
}

function hexToRgb(hex: string): string {
  const h = hex.replace("#", "");
  const n = parseInt(h, 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}
