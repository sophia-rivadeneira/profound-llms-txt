"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { MessageCard } from "@/components/message-card";
import { api, type Monitor, type MonitorPatch } from "@/lib/api";

export function MonitorSettings({ siteId }: { siteId: number }) {
  const qc = useQueryClient();
  const monitorQuery = useQuery({
    queryKey: ["monitor", siteId],
    queryFn: () => api.getMonitor(siteId),
  });

  const patchMutation = useMutation({
    mutationFn: (body: MonitorPatch) => api.patchMonitor(siteId, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["monitor", siteId] }); }
  });

  const monitor = monitorQuery.data;

  if (monitorQuery.isLoading) {
    return <MessageCard title="Loading monitor settings…" />;
  }

  if (monitorQuery.isError || !monitor) {
    return (
      <MessageCard
        tone="error"
        title="Could not load monitor settings"
        description="Refresh the page to try again."
      />
    );
  }

  return (
    <MonitorPanel monitor={monitor} onPatch={patchMutation.mutate}  pending={patchMutation.isPending} />
  );
}

function MonitorPanel({
  monitor,
  onPatch,
  pending,
}: {
  monitor: Monitor;
  onPatch: (body: MonitorPatch) => void;
  pending: boolean;
}) {
  const [intervalInput, setIntervalInput] = useState(String(monitor.interval_hours));
  const [prevHours, setPrevHours] = useState(monitor.interval_hours);


  if (prevHours !== monitor.interval_hours) {
    setPrevHours(monitor.interval_hours);
    setIntervalInput(String(monitor.interval_hours));
  }

  const parsed = Number(intervalInput);
  const intervalValid =  /^\d+$/.test(intervalInput) && parsed >= 1 && parsed <= 168;
  const intervalChanged = intervalValid && parsed !== monitor.interval_hours;

  const togglePause = () => {
    onPatch({ is_active: !monitor.is_active });
  };

  const saveInterval = () => {
    if (intervalChanged) onPatch({ interval_hours: parsed });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Monitoring</CardTitle>
      </CardHeader>
      <CardContent className="pb-4 flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1 text-sm">
            <p className="font-medium">
              {monitor.is_active ? "Active" : "Paused"}
            </p>
            <p className="text-muted-foreground">
              {monitor.is_active
                ? `Checking every ${monitor.interval_hours}h. Last: ${formatTime(monitor.last_checked_at)}. Next: ${formatTime(monitor.next_check_at)}.`
                : "Automatic checks are off. You can still re-crawl manually."}
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={togglePause} disabled={pending} >
            {monitor.is_active ? "Pause" : "Resume"}
          </Button>
        </div>

        {monitor.is_active && (
          <div className="flex items-end gap-2">
            <div className="flex flex-col gap-1">
              <label
                htmlFor={`monitor-interval-${monitor.site_id}`}
                className="text-xs text-muted-foreground"
              >
                Check every N hours (1–168)
              </label>
              <Input
                id={`monitor-interval-${monitor.site_id}`}
                type="number"
                min={1}
                max={168}
                value={intervalInput}
                onChange={(e) => setIntervalInput(e.target.value)}
                className="w-28"
                aria-invalid={!intervalValid}
              />
            </div>
            <Button
              size="sm"
              onClick={saveInterval}
              disabled={!intervalChanged || pending}
            >
              Save
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function formatTime(iso: string | null): string {
  if (!iso) return "never";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  });
}
