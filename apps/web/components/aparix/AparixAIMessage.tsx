"use client";

import { clsx } from "clsx";
import { useState } from "react";

import type { ToolCall } from "@/lib/api";

interface AparixAIMessageProps {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
}

export function AparixAIMessage({ role, content, toolCalls }: AparixAIMessageProps) {
  const [showSources, setShowSources] = useState(false);
  const isAssistant = role === "assistant";

  return (
    <div className={clsx("flex", isAssistant ? "justify-start" : "justify-end")}>
      <div className={clsx("max-w-[80%]", isAssistant ? "" : "text-right")}>
        <div
          className={clsx(
            "rounded-md px-3 py-2 text-sm",
            isAssistant ? "border border-border bg-surface" : "bg-accent text-accent-foreground"
          )}
        >
          {content}
        </div>
        {isAssistant && toolCalls && toolCalls.length > 0 && (
          <div className="mt-1">
            <button
              onClick={() => setShowSources((v) => !v)}
              className="text-xs text-accent hover:underline"
            >
              {showSources ? "Hide" : "View"} data source{toolCalls.length > 1 ? "s" : ""} ({toolCalls.length})
            </button>
            {showSources && (
              <div className="mt-1 space-y-1">
                {toolCalls.map((call, i) => (
                  <div key={i} className="rounded border border-border bg-surface p-2 text-left">
                    <div className="font-mono-nums text-[11px] text-accent">{call.tool_name}()</div>
                    <pre className="mt-1 overflow-x-auto text-[11px] text-muted-foreground">
                      {JSON.stringify(call.result, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
