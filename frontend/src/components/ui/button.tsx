import * as React from "react";
import { cn } from "@/lib/utils";

export function Button({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={cn("inline-flex h-11 items-center justify-center gap-2 rounded-full bg-[var(--deep)] px-5 text-sm font-medium text-white transition hover:bg-[var(--coral)] disabled:cursor-wait disabled:opacity-60", className)} {...props} />;
}