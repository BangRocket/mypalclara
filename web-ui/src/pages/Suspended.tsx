import { useAuth } from "@/auth/AuthProvider";
import { Navigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function SuspendedPage() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  // If not logged in, redirect to login
  if (!user) return <Navigate to="/login" replace />;

  // If active, redirect to home
  if (user.status === "active") return <Navigate to="/" replace />;

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <div className="w-full max-w-md space-y-6 text-center px-4">
        <div>
          <h1 className="text-3xl font-bold text-primary">Clara</h1>
          <p className="text-muted-foreground mt-1">Your personal AI assistant</p>
        </div>

        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="w-16 h-16 mx-auto rounded-full bg-red-500/20 flex items-center justify-center">
              <svg
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-red-500"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
              </svg>
            </div>

            <h2 className="text-xl font-semibold">Account Suspended</h2>

            <p className="text-muted-foreground">
              Your account has been suspended. If you believe this is an error,
              please contact an administrator.
            </p>
          </CardContent>
        </Card>

        <Button
          variant="ghost"
          onClick={logout}
          className="text-sm underline"
        >
          Sign out
        </Button>
      </div>
    </div>
  );
}
