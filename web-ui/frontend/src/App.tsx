import { Routes, Route, Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/auth/AuthProvider";
import { AppLayout } from "@/components/layout/AppLayout";
import { ChatRuntimeProvider } from "@/components/chat/ChatRuntimeProvider";
import { useWebSocket } from "@/hooks/useWebSocket";
import { LoginPage } from "@/pages/Login";
import { KnowledgeBasePage } from "@/pages/KnowledgeBase";
import { ChatPage } from "@/pages/Chat";
import { GraphExplorerPage } from "@/pages/GraphExplorer";
import { SettingsPage } from "@/pages/Settings";
import { IntentionsPage } from "@/pages/Intentions";
import { OAuthCallback } from "@/auth/OAuthCallback";
import { PendingApproval } from "@/pages/PendingApproval";
import { SuspendedPage } from "@/pages/Suspended";
import { AdminUsersPage } from "@/pages/AdminUsers";
import Lobby from "@/pages/Lobby";
import Blackjack from "@/pages/Blackjack";
import Checkers from "@/pages/Checkers";
import GameHistory from "@/pages/GameHistory";
import Replay from "@/pages/Replay";
import { api } from "@/api/client";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.status === "pending") return <Navigate to="/pending" replace />;
  if (user.status === "suspended") return <Navigate to="/suspended" replace />;
  return <>{children}</>;
}

/** Connects WebSocket when authenticated. Wraps children in ChatRuntimeProvider. */
function WebSocketBridge({ children }: { children: React.ReactNode }) {
  useWebSocket();
  return <ChatRuntimeProvider>{children}</ChatRuntimeProvider>;
}

/** Routes to the correct game component based on game_type. */
function GameRouter() {
  const { id } = useParams();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data, isLoading } = useQuery<any>({
    queryKey: ["game", id],
    queryFn: () => api.games.show(id!),
  });
  if (isLoading) return <div style={{ minHeight: "100vh", background: "#0a0a0a", display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontFamily: "monospace" }}>Loading...</div>;
  if (!data?.game) return <div style={{ minHeight: "100vh", background: "#0a0a0a", display: "flex", alignItems: "center", justifyContent: "center", color: "#ef4444", fontFamily: "monospace" }}>Game not found</div>;
  if (data.game.game_type === "checkers") return <Checkers game={data.game} />;
  return <Blackjack game={data.game} />;
}

export function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback/:provider" element={<OAuthCallback />} />
      <Route path="/pending" element={<PendingApproval />} />
      <Route path="/suspended" element={<SuspendedPage />} />

      {/* Protected — WebSocket + ChatRuntime hoisted to wrap all routes */}
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <WebSocketBridge>
              <AppLayout>
                <Routes>
                  <Route path="/" element={<ChatPage />} />
                  <Route path="/knowledge" element={<KnowledgeBasePage />} />
                  <Route path="/graph" element={<GraphExplorerPage />} />
                  <Route path="/intentions" element={<IntentionsPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/admin/users" element={<AdminUsersPage />} />
                  <Route path="/games" element={<Lobby />} />
                  <Route path="/games/history" element={<GameHistory />} />
                  <Route path="/games/history/:id" element={<Replay />} />
                  <Route path="/games/:id" element={<GameRouter />} />
                </Routes>
              </AppLayout>
            </WebSocketBridge>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
