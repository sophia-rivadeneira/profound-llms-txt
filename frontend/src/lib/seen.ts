import { useCallback, useSyncExternalStore } from "react";

const STORAGE_KEY = "profound:seen-events";

type SeenMap = Record<string, number>;

const listeners = new Set<() => void>();

function notify() {
  for (const l of listeners) l();
}

function read(): SeenMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

function write(map: SeenMap) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // ignore quota errors
  }
}

export function getLastSeenEventId(siteId: number): number {
  return read()[String(siteId)] ?? 0;
}

export function markSiteSeen(siteId: number, latestEventId: number) {
  const map = read();
  const current = map[String(siteId)] ?? 0;
  if (latestEventId > current) {
    map[String(siteId)] = latestEventId;
    write(map);
    notify();
  }
}

function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
}

export function useLastSeenEventId(siteId: number): number {
  const getSnapshot = useCallback(
    () => getLastSeenEventId(siteId),
    [siteId],
  );
  return useSyncExternalStore(subscribe, getSnapshot, () => 0);
}
