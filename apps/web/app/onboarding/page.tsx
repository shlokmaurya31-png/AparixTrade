"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AparixComplexityControl } from "@/components/aparix/AparixComplexityControl";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/use-auth";

const EXPERIENCE_LEVELS = [
  { id: "beginner", label: "Beginner", description: "New to investing" },
  { id: "retail", label: "Retail investor", description: "Comfortable with the basics" },
  { id: "active_trader", label: "Active trader", description: "Trade regularly" },
  { id: "hni", label: "HNI / advisor", description: "Manage significant capital" },
  { id: "professional", label: "Professional", description: "Analyst, PM, or quant" },
] as const;

export default function OnboardingPage() {
  useRequireAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [experienceLevel, setExperienceLevel] = useState<string>("beginner");
  const [complexityLevel, setComplexityLevel] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onContinue() {
    setSaving(true);
    setError(null);
    try {
      const updatedUser = await api.users.updatePreferences({
        experience_level: experienceLevel,
        complexity_level: complexityLevel,
        ai_mode: complexityLevel >= 3 ? "analyst" : "simple",
      });
      // useRequireAuth() on this page (and the dashboard layout after
      // redirect) both read the ["me"] query — without this it stays
      // cached at pre-onboarding values until staleTime lapses.
      queryClient.setQueryData(["me"], updatedUser);

      const portfolios = await api.portfolios.list();
      if (portfolios.length === 0) {
        await api.portfolios.create({ name: "My Portfolio", kind: "long_term" });
      }

      router.push("/home");
    } catch {
      setError("Couldn't save your preferences. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto min-h-screen max-w-xl px-4 py-16">
      <h1 className="text-xl font-semibold">Set up Aparix</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        This tunes how much detail Aparix shows you — you can change it anytime.
      </p>

      <div className="mt-8">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Your experience level
        </h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {EXPERIENCE_LEVELS.map((level) => (
            <button
              key={level.id}
              onClick={() => setExperienceLevel(level.id)}
              className={`rounded-md border p-3 text-left transition-colors ${
                experienceLevel === level.id
                  ? "border-accent bg-accent/10"
                  : "border-border hover:bg-surface-hover"
              }`}
            >
              <div className="text-sm font-medium">{level.label}</div>
              <div className="text-xs text-muted-foreground">{level.description}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Complexity level
        </h2>
        <AparixComplexityControl value={complexityLevel} onChange={setComplexityLevel} />
      </div>

      {error && <p className="mt-4 text-sm text-negative">{error}</p>}

      <button
        onClick={onContinue}
        disabled={saving}
        className="mt-8 w-full rounded bg-accent py-2.5 text-sm font-medium text-accent-foreground disabled:opacity-50"
      >
        {saving ? "Setting up…" : "Get started"}
      </button>
    </div>
  );
}
