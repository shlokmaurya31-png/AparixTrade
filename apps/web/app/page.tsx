"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { getStoredToken } from "@/lib/api";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getStoredToken() ? "/home" : "/login");
  }, [router]);

  return null;
}
