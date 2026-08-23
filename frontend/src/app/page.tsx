"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, ArrowUpRight, CircleAlert, Image as ImageIcon, Leaf, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8765";
type Stats = { activity_count: number; memory_count: number; generation_count: number; last_generation: number };
type Memory = { id: number; created_at: number; summary: string };

function formatDate(timestamp: number) {
  if (!timestamp) return "Awaiting first generation";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(timestamp * 1000);
}

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    Promise.all([fetch(`${API}/api/stats`).then((response) => response.json()), fetch(`${API}/api/memory`).then((response) => response.json())])
      .then(([nextStats, nextMemories]) => { setStats(nextStats); setMemories(nextMemories); })
      .catch(() => setMessage("Start the local service to connect your archive."));
  }, [refreshKey]);

  async function generate() {
    setBusy(true); setMessage("Composing your next world...");
    try {
      const response = await fetch(`${API}/api/generate`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Generation failed");
      setMessage(`New wallpaper generated at ${formatDate(Date.now() / 1000)}.`); setRefreshKey((key) => key + 1);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Generation failed."); }
    finally { setBusy(false); }
  }

  const latest = stats?.last_generation ?? 0;
  const metrics = [["Activity captured", stats?.activity_count ?? 0, Activity], ["Memory fragments", stats?.memory_count ?? 0, Leaf], ["Worlds generated", stats?.generation_count ?? 0, Sparkles], ["Service status", stats ? "Online" : "Offline", stats ? Activity : CircleAlert]] as const;

  return <main className="mx-auto min-h-screen w-full max-w-[1440px] px-5 py-6 text-[var(--ink)] sm:px-8 lg:px-12 lg:py-10">
    <header className="flex items-center justify-between border-b border-[var(--line)] pb-5"><div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-full bg-[var(--deep)] text-[var(--paper)]"><Leaf size={17} /></div><span className="font-mono text-xs font-medium uppercase tracking-[0.18em]">Memory Wallpaper</span></div><button aria-label="Refresh archive" onClick={() => setRefreshKey((key) => key + 1)} className="rounded-full p-2 text-stone-500 transition hover:bg-white hover:text-[var(--ink)]"><RefreshCw size={17} /></button></header>
    <section className="grid gap-8 pb-14 pt-12 lg:grid-cols-[1fr_1.22fr] lg:items-end lg:gap-16 lg:pt-20"><motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .6 }}><Badge><span className="mr-2 inline-block size-1.5 rounded-full bg-[var(--coral)]" />Private local archive</Badge><h1 className="mt-6 max-w-xl font-serif text-5xl leading-[.98] tracking-[-0.04em] sm:text-7xl">A wallpaper that remembers <i className="text-[var(--coral)]">where you&apos;ve been.</i></h1><p className="mt-6 max-w-md text-base leading-7 text-stone-600">Your browsing rhythm becomes a quiet visual world. Metadata stays on this machine until you choose to create something new.</p><Button onClick={generate} disabled={busy} className="mt-8">{busy ? <Loader2 className="animate-spin" /> : <Sparkles />} Generate next wallpaper <ArrowUpRight /></Button><AnimatePresence mode="wait"><motion.p key={message} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 min-h-5 font-mono text-[11px] uppercase tracking-wider text-stone-500">{message}</motion.p></AnimatePresence></motion.div>
      <motion.div initial={{ opacity: 0, scale: .98 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: .15, duration: .7 }}><Card className="relative aspect-[16/10] overflow-hidden bg-[var(--deep)] p-0">{latest ? <img key={latest} src={`${API}/api/wallpaper/latest?v=${latest}`} alt="Latest generated wallpaper" className="h-full w-full object-cover opacity-90" /> : <div className="absolute inset-0 grid place-items-center"><div className="text-center text-white/60"><ImageIcon className="mx-auto mb-3" size={30} strokeWidth={1.2} /><p className="font-mono text-[10px] uppercase tracking-widest">Your first image is waiting</p></div></div>}<div className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-transparent" /><div className="absolute left-5 top-5 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[.16em] text-white/75"><ImageIcon size={14} /> Current atmosphere</div><div className="absolute bottom-5 left-5 right-5 flex items-end justify-between text-white"><div><p className="font-serif text-2xl italic">The evolving world</p><p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-white/60">{formatDate(latest)}</p></div><span className="grid size-10 place-items-center rounded-full border border-white/30"><ArrowUpRight size={17} /></span></div></Card></motion.div>
    </section>
    <section className="border-y border-[var(--line)] py-5"><div className="grid grid-cols-2 gap-5 sm:grid-cols-4">{metrics.map(([label, value, Icon], index) => <div key={label} className={`${index ? "border-l border-[var(--line)] pl-5" : ""}`}><Icon size={15} className="mb-3 text-[var(--coral)]" /><p className="font-mono text-[10px] uppercase tracking-widest text-stone-500">{label}</p><p className="mt-1 text-xl font-medium">{value}</p></div>)}</div></section>
    <section className="grid gap-8 py-14 lg:grid-cols-[.8fr_1.2fr]"><div><p className="font-mono text-[10px] uppercase tracking-[.2em] text-[var(--coral)]">01 / Visual memory</p><h2 className="mt-3 font-serif text-4xl tracking-[-.03em]">What the archive is carrying</h2><p className="mt-4 max-w-sm leading-7 text-stone-600">A compact, evolving record of themes and moods. The model sees browser metadata, never page contents.</p></div><div className="space-y-3">{memories.length ? memories.slice().reverse().map((memory, index) => <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * .08 }} key={memory.id} className="border-b border-[var(--line)] py-4"><div className="flex items-baseline justify-between gap-4"><span className="font-mono text-[10px] uppercase tracking-widest text-stone-400">Fragment {String(memories.length - index).padStart(2, "0")}</span><span className="font-mono text-[10px] text-stone-400">{formatDate(memory.created_at)}</span></div><p className="mt-2 text-lg leading-7">{memory.summary}</p></motion.div>) : <div className="border border-dashed border-[var(--line)] p-8 text-center font-mono text-xs uppercase tracking-widest text-stone-500">No memory fragments yet</div>}</div></section>
    <footer className="flex flex-col gap-2 border-t border-[var(--line)] pt-5 font-mono text-[10px] uppercase tracking-widest text-stone-400 sm:flex-row sm:justify-between"><span>Local first / Always yours</span><span>127.0.0.1:8765</span></footer>
  </main>;
}