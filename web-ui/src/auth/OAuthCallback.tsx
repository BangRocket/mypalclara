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
      <div className="flex items-center justify-center min-h-screen bg-surface">
        <div className="bg-surface-raised border border-danger/30 rounded-xl p-8 max-w-md text-center">
          <h2 className="text-lg font-semibold text-danger mb-2">Authentication Failed</h2>
          <p className="text-text-secondary">{error}</p>
          <button
            onClick={() => navigate("/login")}
            className="mt-4 px-4 py-2 bg-primary hover:bg-primary/85 rounded-lg text-white transition"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-surface">
      <div className="text-text-secondary">Authenticating...</div>
    </div>
  );
}
