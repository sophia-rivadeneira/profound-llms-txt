"use client";

import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type ChangeEvent } from "@/lib/api";

const CHANGE_TYPES = [
  {
    field: "pages_added" as const,
    prefix: "+",
    label: "added",
    color: "text-green-700 dark:text-green-400",
  },
  {
    field: "pages_removed" as const,
    prefix: "-",
    label: "removed",
    color: "text-red-700 dark:text-red-400",
  },
  {
    field: "pages_modified" as const,
    prefix: "~",
    label: "modified",
    color: "text-amber-700 dark:text-amber-400",
  },
];

export function ChangeTimeline({
  events,
  lastSeen,
  reviewTick,
  onOpen,
}: {
  events: ChangeEvent[];
  lastSeen: number;
  reviewTick: number;
  onOpen: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Change timeline</CardTitle>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No changes detected yet. We&apos;ll track additions, removals, and
            modified pages here after each crawl.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {events.map((e) => (
              <TimelineRow
                key={e.id}
                event={e}
                unread={e.id > lastSeen}
                expandTrigger={e.id > lastSeen ? reviewTick : 0}
                onOpen={onOpen}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function TimelineRow({
  event,
  unread,
  expandTrigger,
  onOpen,
}: {
  event: ChangeEvent;
  unread: boolean;
  expandTrigger: number;
  onOpen: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [prevTrigger, setPrevTrigger] = useState(expandTrigger);

  if (expandTrigger !== prevTrigger) {
    setPrevTrigger(expandTrigger);
    if (expandTrigger > 0) setOpen(true);
  }

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) onOpen();
  };

  return (
    <li className={`rounded-xl border border-border/60 p-3 transition-colors ${unread ? "bg-card/50" : ""}`} >
      <button onClick={toggle} className="w-full flex items-center justify-between text-left">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">
            {new Date(event.detected_at).toLocaleString()}
          </span>
          <span className="text-xs text-muted-foreground">
            {event.triggered_by === "scheduled" ? "automatic check" : "manual refresh"}
          </span>
          {unread && <Badge>New</Badge>}
        </div>
        <div className="flex items-center gap-3 text-sm font-mono">
          {CHANGE_TYPES.map(({ field, prefix, label, color }) => {
            const count = event[field];
            if (count === 0) return null;
            return (
              <span key={label} className={`${color} flex items-center gap-1`}>
                <span className="font-mono">{prefix}{count}</span>
                <span className="text-xs font-sans font-normal opacity-70">
                  {count === 1 ? `page ${label}` : `pages ${label}`}
                </span>
              </span>
            );
          })}
          {open ? (
            <ChevronUpIcon className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDownIcon className="size-4 text-muted-foreground" />
          )}
        </div>
      </button>
      {open && event.summary && (
        <ul className="mt-2 flex flex-col gap-0.5 text-sm text-muted-foreground list-disc list-inside">
          {event.summary.split(";").map((item) => item.trim()).filter(Boolean).map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </li>
  );
}
