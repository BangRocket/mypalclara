import { Routes, Route, Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/auth/AuthProvider";
import { ChatRuntimeProvider } from "@/components/chat/ChatRuntimeProvider";
import { FeatureLayout } from "@/components/layout/FeatureLayout";
import { useWebSocket } from "@/hooks/useWebSocket";
import { LoginPage } from "@/pages/Login";
import { HomePage } from "@/pages/HomePage";
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

      {/* Protected — Home page (no WebSocket, no sidebar) */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />

      {/* Protected — Chat (WebSocket scoped here only) */}
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <WebSocketBridge>
              <FeatureLayout title="Chat">
                <ChatPage />
              </FeatureLayout>
            </WebSocketBridge>
          </ProtectedRoute>
        }
      />

      {/* Protected — Feature pages (no WebSocket, FeatureLayout wrapper) */}
      <Route
        path="/knowledge"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Knowledge Base">
              <KnowledgeBasePage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/graph"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Memory Graph">
              <GraphExplorerPage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/intentions"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Intentions">
              <IntentionsPage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Settings">
              <SettingsPage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Admin">
              <AdminUsersPage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />

      {/* Protected — Games (FeatureLayout for lobby/history, own layout for active games) */}
      <Route
        path="/games"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Games">
              <Lobby />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/games/history"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Game History">
              <GameHistory />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/games/history/:id"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Replay">
              <Replay />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/games/:id"
        element={
          <ProtectedRoute>
            <GameRouter />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
