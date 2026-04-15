"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export function LlmsPreview({
  siteId,
  content,
}: {
  siteId: number;
  content: string;
}) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">llms.txt</CardTitle>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={onCopy}>
            {copied ? "Copied!" : "Copy"}
          </Button>
          <Button size="sm" variant="outline" asChild>
            <a href={api.llmsRawUrl(siteId)} download="llms.txt">
              Download
            </a>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <pre className="text-xs leading-relaxed max-h-96 overflow-auto rounded-md bg-muted p-4 font-mono whitespace-pre-wrap break-words">
          {content}
        </pre>
      </CardContent>
    </Card>
  );
}
