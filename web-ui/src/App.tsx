import { Routes, Route, Navigate } from "react-router-dom";
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
                </Routes>
              </AppLayout>
            </WebSocketBridge>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
