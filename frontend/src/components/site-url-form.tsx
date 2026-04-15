"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";

export function SiteUrlForm() {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (raw: string) => api.createSite(raw),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["sites"] });
      router.push(`/sites/${data.site.slug ?? data.site.domain}`);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong. Please try again.");
      }
    },
  });

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const trimmed = url.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="flex gap-2">
        <Input type="url" inputMode="url" placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)}
         disabled={mutation.isPending}
          required
          className="h-11 text-base"
        />
        <Button type="submit" disabled={mutation.isPending || !url.trim()} className="h-11 px-6" >
          {mutation.isPending ? "Starting…" : "Generate"}
        </Button>
      </div>
      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        <p className="text-sm text-muted-foreground">
          Paste any website URL. We&apos;ll crawl it and produce an llms.txt you can
          drop in today.
        </p>
      )}
    </form>
  );
}
