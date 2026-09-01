"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AparixBadge, DemoDataBadge } from "@/components/aparix/AparixBadge";
import { AparixCard } from "@/components/aparix/AparixCard";
import { AparixTable } from "@/components/aparix/AparixTable";
import { api, ApiError, type AparixEvent, type EventImpact, type NewsArticle } from "@/lib/api";
import { usePrimaryPortfolio } from "@/lib/use-portfolio";

const SEVERITY_TONE = { low: "neutral", medium: "warning", high: "negative" } as const;
const DIRECTION_TONE = { positive: "positive", negative: "negative", neutral: "neutral" } as const;

function formatInr(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    value
  );
}

function relativeTime(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24));
  if (days <= 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

export default function EventsPage() {
  const { portfolio } = usePrimaryPortfolio();
  const events = useQuery({ queryKey: ["events"], queryFn: api.events.list });
  const news = useQuery({ queryKey: ["news"], queryFn: api.news.list });

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [impact, setImpact] = useState<EventImpact | null>(null);
  const [impactError, setImpactError] = useState<string | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);

  async function viewImpact(event: AparixEvent) {
    if (!portfolio) return;
    if (expandedId === event.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(event.id);
    setImpact(null);
    setImpactError(null);
    setImpactLoading(true);
    try {
      setImpact(await api.events.impact(event.id, portfolio.id));
    } catch (err) {
      setImpactError(err instanceof ApiError ? err.message : "Couldn't assess impact for this event.");
    } finally {
      setImpactLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Market Events</h1>
          <p className="text-xs text-muted-foreground">
            Mostly seeded illustrative events; some are real, ingested news classified by keyword (see
            &ldquo;Recent news&rdquo; below) — see an event&rsquo;s impact on your portfolio below.
          </p>
        </div>
        <DemoDataBadge />
      </div>

      <div className="space-y-3">
        {events.data?.map((event) => (
          <AparixCard key={event.id}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="mb-1.5 flex flex-wrap gap-1.5">
                  <AparixBadge tone={SEVERITY_TONE[event.severity]}>{event.severity}</AparixBadge>
                  <AparixBadge tone={DIRECTION_TONE[event.direction]}>{event.direction}</AparixBadge>
                  <AparixBadge tone="accent">{event.primary_target}</AparixBadge>
                  <AparixBadge tone="neutral">{event.event_type.replace("_", " ")}</AparixBadge>
                </div>
                <h3 className="text-sm font-medium">{event.headline}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{event.summary}</p>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {event.region ?? "—"} · {relativeTime(event.published_at)}
                </p>
              </div>
              <button
                onClick={() => viewImpact(event)}
                disabled={!portfolio}
                className="shrink-0 rounded border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface-hover disabled:opacity-50"
              >
                {expandedId === event.id ? "Hide impact" : "View impact"}
              </button>
            </div>

            {expandedId === event.id && (
              <div className="mt-3 border-t border-border pt-3 text-sm">
                {impactLoading && <p className="text-muted-foreground">Assessing impact…</p>}
                {impactError && <p className="text-negative">{impactError}</p>}
                {impact && !impactLoading && (
                  <div>
                    <p>
                      Estimated impact:{" "}
                      <span className={impact.estimated_impact >= 0 ? "text-positive" : "text-negative"}>
                        {formatInr(impact.estimated_impact)} ({impact.estimated_impact_pct.toFixed(2)}%)
                      </span>{" "}
                      — portfolio value {formatInr(impact.portfolio_value_before)} →{" "}
                      {formatInr(impact.portfolio_value_after)}
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">{impact.assumptions}</p>
                  </div>
                )}
              </div>
            )}
          </AparixCard>
        ))}
        {events.data?.length === 0 && <p className="text-sm text-muted-foreground">No events yet.</p>}
      </div>

      <AparixCard title="Recent news">
        <p className="mb-3 text-xs text-muted-foreground">
          Ingested articles — real when the API is configured with a live source (NEWS_PROVIDER=rss), an
          illustrative fixed set otherwise. Most articles are routine and never become an event above; only
          ones a keyword classifier judges market-moving do.
        </p>
        <AparixTable<NewsArticle>
          columns={[
            {
              header: "Title",
              render: (a) => (
                <a href={a.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                  {a.title}
                </a>
              ),
            },
            { header: "Publisher", render: (a) => <span className="text-muted-foreground">{a.publisher}</span> },
            { header: "Published", render: (a) => new Date(a.published_at).toLocaleString() },
            {
              header: "Event?",
              render: (a) => (a.event_id ? <AparixBadge tone="accent">Yes</AparixBadge> : "—"),
            },
          ]}
          rows={news.data ?? []}
          keyFor={(a) => a.id}
          emptyMessage="No news ingested yet."
        />
      </AparixCard>
    </div>
  );
}
