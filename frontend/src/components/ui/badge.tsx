import * as React from "react";
import { cn } from "@/lib/utils";

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center border border-[var(--line)] bg-[var(--paper)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-stone-600", className)} {...props} />;
}