"use client";

import { useMemo } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { type PageDataRow } from "@/lib/api";

export function PagesBySection({ pages }: { pages: PageDataRow[] }) {
  const grouped = useMemo(() => {
    const map = new Map<string, PageDataRow[]>();
    for (const p of pages) {
      const key = p.section ?? "General";
      const label = p.is_optional ? `Optional · ${key}` : key;
      if (!map.has(label)) map.set(label, []);
      map.get(label)!.push(p);
    }
    return Array.from(map.entries());
  }, [pages]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Pages ({pages.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <Accordion type="multiple" defaultValue={[grouped[0]?.[0] ?? ""]}>
          {grouped.map(([section, sectionPages]) => (
            <AccordionItem key={section} value={section}>
              <AccordionTrigger className="text-sm font-medium">
                <span className="flex items-center gap-2">
                  {section}
                  <span className="text-xs text-muted-foreground tabular-nums font-normal">
                    {sectionPages.length} {sectionPages.length === 1 ? "page" : "pages"}
                  </span>
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <ul className="flex flex-col divide-y divide-border/40 pb-1">
                  {sectionPages.map((p) => (
                    <li key={p.id} className="flex flex-col px-2 py-2">
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-medium hover:underline"
                      >
                        {p.title ?? p.url}
                      </a>
                      {p.description && (
                        <span className="text-xs text-muted-foreground mt-0.5">
                          {p.description}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  );
}
