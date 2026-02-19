import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { auth, setToken } from "@/api/client";
import { useAuth } from "@/auth/AuthProvider";

export function OAuthCallback() {
  const { provider } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code || !provider) {
      setError("Missing authorization code");
      return;
    }

    auth
      .callback(provider, code)
      .then(async ({ token }) => {
        if (token) setToken(token);
        await refresh();
        navigate("/", { replace: true });
      })
      .catch((e) => setError(e.message));
  }, [provider, searchParams, navigate, refresh]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="max-w-md rounded-xl border border-destructive/30 bg-card p-8 text-center">
          <h2 className="mb-2 text-lg font-semibold text-destructive">
            Authentication Failed
          </h2>
          <p className="text-muted-foreground">{error}</p>
          <button
            onClick={() => navigate("/login")}
            className="mt-4 rounded-lg bg-primary px-4 py-2 text-white transition hover:bg-primary/85"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-muted-foreground">Authenticating...</div>
    </div>
  );
}
