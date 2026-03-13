import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { AppLayout } from "@/components/layout/AppLayout";
import { ChatRuntimeProvider } from "@/components/chat/ChatRuntimeProvider";
import { useWebSocket } from "@/hooks/useWebSocket";
import { KnowledgeBasePage } from "@/pages/KnowledgeBase";
import { ChatPage } from "@/pages/Chat";
import { SettingsPage } from "@/pages/Settings";
import { OAuthCallback } from "@/auth/OAuthCallback";

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
      <Route path="/auth/callback/:provider" element={<OAuthCallback />} />

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
                  <Route path="/settings" element={<SettingsPage />} />
                </Routes>
              </AppLayout>
            </WebSocketBridge>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
