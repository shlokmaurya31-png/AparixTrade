"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { api, getStoredToken, setStoredToken } from "@/lib/api";

export function useCurrentUser() {
  return useQuery({
    queryKey: ["me"],
    queryFn: api.auth.me,
    enabled: Boolean(getStoredToken()),
    retry: false,
  });
}

/** Redirects to /login if there's no token or the token is invalid. Use at
 * the top of any authenticated page/layout — Phase 1 has no server-side
 * session, so route protection is client-side (see docs/ARCHITECTURE.md §6). */
export function useRequireAuth() {
  const router = useRouter();
  const query = useCurrentUser();

  useEffect(() => {
    if (!getStoredToken()) {
      router.replace("/login");
      return;
    }
    if (query.isError) {
      setStoredToken(null);
      router.replace("/login");
    }
  }, [query.isError, router]);

  return query;
}

export function useLogout() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return () => {
    setStoredToken(null);
    queryClient.clear();
    router.replace("/login");
  };
}
