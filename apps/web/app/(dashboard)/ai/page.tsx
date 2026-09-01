"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AparixAIMessage } from "@/components/aparix/AparixAIMessage";
import { ComingSoonBadge } from "@/components/aparix/AparixBadge";
import { AparixCard } from "@/components/aparix/AparixCard";
import { api, ApiError, type ToolCall } from "@/lib/api";
import { useCurrentUser } from "@/lib/use-auth";
import { usePrimaryPortfolio } from "@/lib/use-portfolio";

interface Message {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
}

// A mode's label always exists; whether it's a real style variant right now
// depends on which AI provider is active (see GET /api/v1/ai/config) — a
// hardcoded "implemented" flag would silently go stale the moment the
// provider changes, so that comes from the API, not from this list.
const MODE_LABELS: Record<string, string> = {
  simple: "Simple",
  quant: "Quant",
  analyst: "Analyst",
  risk_officer: "Risk Officer",
  portfolio_manager: "Portfolio Manager",
  macro_economist: "Macro Economist",
  options_specialist: "Options Specialist",
  researcher: "Researcher",
};
const MODE_ORDER = Object.keys(MODE_LABELS);

const SUGGESTIONS = [
  "How is my portfolio doing?",
  "What is my biggest sector exposure?",
  "What is my biggest holding?",
  "How risky is my portfolio?",
];

export default function AiTerminalPage() {
  const { portfolio } = usePrimaryPortfolio();
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();
  const aiConfig = useQuery({ queryKey: ["ai-config"], queryFn: api.ai.config });
  const searchParams = useSearchParams();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [sending, setSending] = useState(false);
  const [modeSaving, setModeSaving] = useState<string | null>(null);
  const prefilledQuestionSent = useRef(false);

  const activeMode = user?.preferences.ai_mode ?? "simple";
  const supportedModes = new Set(aiConfig.data?.supported_modes ?? ["simple"]);

  async function selectMode(modeId: string) {
    if (modeId === activeMode) return;
    setModeSaving(modeId);
    try {
      const updatedUser = await api.users.updatePreferences({ ai_mode: modeId });
      queryClient.setQueryData(["me"], updatedUser);
    } finally {
      setModeSaving(null);
    }
  }

  async function sendMessage(text: string) {
    if (!portfolio || !text.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);
    try {
      const response = await api.ai.chat({ portfolio_id: portfolio.id, message: text, session_id: sessionId });
      setSessionId(response.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: response.message, toolCalls: response.tool_calls }]);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${message}` }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-6.5rem)] max-w-3xl flex-col">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-lg font-semibold">AI Terminal</h1>
        <div className="flex flex-wrap justify-end gap-1.5">
          {MODE_ORDER.map((modeId) => {
            const implemented = supportedModes.has(modeId);
            const active = modeId === activeMode;
            return (
              <button
                key={modeId}
                type="button"
                disabled={!implemented || modeSaving === modeId}
                onClick={() => selectMode(modeId)}
                className={`rounded border px-2 py-1 text-xs transition-colors disabled:cursor-not-allowed ${
                  active
                    ? "border-accent bg-accent text-accent-foreground"
                    : implemented
                      ? "border-accent/40 text-accent hover:bg-surface-hover"
                      : "border-border text-muted-foreground"
                }`}
                title={implemented ? "Switch AI response style" : "Coming soon — needs an options/RAG data source"}
              >
                {MODE_LABELS[modeId]}
                {!implemented && <ComingSoonBadge className="ml-1" />}
              </button>
            );
          })}
        </div>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        {aiConfig.data
          ? aiConfig.data.provider === "ollama"
            ? `Powered by Ollama (${aiConfig.data.model}), running locally.`
            : "Powered by a mock provider in development mode — responses are templated, not model-generated."
          : " "}
      </p>

      <AparixCard className="flex flex-1 flex-col overflow-hidden">
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <p className="text-sm text-muted-foreground">
                Ask about your portfolio. Every number Aparix cites traces back to a real calculation — never
                invented — click &ldquo;View data source&rdquo; on any answer to see it.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className="rounded-full border border-border px-3 py-1 text-xs hover:bg-surface-hover"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <AparixAIMessage key={i} role={m.role} content={m.content} toolCalls={m.toolCalls} />
          ))}
          {sending && <p className="text-sm text-muted-foreground">Aparix is thinking…</p>}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
          className="mt-3 flex shrink-0 gap-2 border-t border-border pt-3"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Aparix anything…"
            className="flex-1 rounded border border-border bg-transparent px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={sending || !portfolio}
            className="rounded bg-accent px-4 py-2 text-sm font-medium text-accent-foreground disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </AparixCard>
    </div>
  );
}
