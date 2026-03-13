import { useAuth } from "@clerk/react";
import { useEffect } from "react";
import { setTokenGetter } from "@/api/client";

/**
 * Bridges Clerk's token system into the API client.
 * Must be mounted inside ClerkProvider. Renders nothing.
 */
export function TokenBridge() {
  const { getToken } = useAuth();
  useEffect(() => {
    setTokenGetter(getToken);
  }, [getToken]);
  return null;
}
