"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createWsTerminal } from "@/lib/api";

interface TermLine {
  id: number;
  timestamp: string;
  output: string;
  level: "info" | "warn" | "error" | "system" | "clear";
  type: string;
}

const LEVEL_CLASS: Record<string, string> = {
  info:   "text-emerald-400",
  warn:   "text-amber-400",
  error:  "text-red-400",
  system: "text-cyan-300 font-bold",
};

const MAX_LINES = 500;

export default function CommandTerminal() {
  const [lines, setLines]         = useState<TermLine[]>([]);
  const [input, setInput]         = useState("");
  const [connected, setConnected] = useState(false);
  const [history, setHistory]     = useState<string[]>([]);
  const [histIdx, setHistIdx]     = useState(-1);

  const wsRef    = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLInputElement>(null);
  const idxRef    = useRef(0);

  const addLine = useCallback((output: string, level: TermLine["level"], type = "OUTPUT") => {
    const id = ++idxRef.current;
    const timestamp = new Date().toLocaleTimeString("en-GB", { hour12: false });
    setLines(prev => {
      const next = [...prev, { id, timestamp, output, level, type }];
      return next.length > MAX_LINES ? next.slice(-MAX_LINES) : next;
    });
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = createWsTerminal();
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          const type  = msg.type  ?? "OUTPUT";
          const level = (msg.level ?? "info") as TermLine["level"];

          if (type === "CLEAR") {
            setLines([]);
            return;
          }
          if (msg.output) addLine(msg.output, level, type);
        } catch {
          addLine(evt.data, "info");
        }
      };

      ws.onerror = () => {
        addLine("[CONSOLE] Connection error.", "error");
      };

      ws.onclose = (e) => {
        setConnected(false);
        if (e.code !== 1000 && e.code !== 4003) {
          setTimeout(connect, 3000);
        }
      };
    } catch (err) {
      addLine(`[CONSOLE] Failed to open connection: ${err}`, "error");
    }
  }, [addLine]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close(1000, "component unmount");
    };
  }, [connect]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  const sendCmd = useCallback(() => {
    const cmd = input.trim();
    if (!cmd) return;

    // Echo input to terminal
    addLine(`ROOT@ORG:~# ${cmd}`, "warn");

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(cmd);
    } else {
      addLine("[CONSOLE] Not connected. Reconnecting...", "error");
      connect();
    }

    setHistory(prev => [cmd, ...prev.slice(0, 99)]);
    setHistIdx(-1);
    setInput("");
  }, [input, addLine, connect]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      sendCmd();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHistIdx(prev => {
        const next = Math.min(prev + 1, history.length - 1);
        setInput(history[next] ?? "");
        return next;
      });
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setHistIdx(prev => {
        const next = Math.max(prev - 1, -1);
        setInput(next === -1 ? "" : history[next] ?? "");
        return next;
      });
    } else if (e.key === "Tab") {
      e.preventDefault();
      const COMMANDS = [
        "help", "status", "soc-metrics", "tail-logs", "devices",
        "isolate ", "revoke-token ", "flush-sessions ", "playbook list",
        "playbook run ", "clear",
      ];
      const match = COMMANDS.find(c => c.startsWith(input));
      if (match) setInput(match);
    }
  }, [sendCmd, history, input]);

  return (
    <div
      className="flex flex-col h-full bg-[#09090f] font-mono text-[12px] leading-relaxed select-text"
      onClick={() => inputRef.current?.focus()}
    >
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-2 border-b border-slate-800/60 bg-[#0a0a12]">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-black tracking-[0.25em] text-slate-500">
            NEXUS COMMAND CONSOLE
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-emerald-500 animate-pulse" : "bg-red-500"
            }`}
          />
          <span className={`text-[9px] tracking-widest ${connected ? "text-emerald-500" : "text-red-400"}`}>
            {connected ? "ONLINE" : "OFFLINE"}
          </span>
          {!connected && (
            <button
              onClick={(e) => { e.stopPropagation(); connect(); }}
              className="text-[9px] text-sky-500 hover:text-sky-300 tracking-widest ml-2"
            >
              RECONNECT
            </button>
          )}
        </div>
      </div>

      {/* Output area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-0.5 custom-scrollbar">
        {lines.length === 0 && (
          <div className="text-slate-700 text-center py-6 text-[11px] tracking-widest">
            AWAITING CONNECTION...
          </div>
        )}
        {lines.map((line) => (
          <div key={line.id} className="flex gap-3 items-start hover:bg-white/[0.02] rounded px-1">
            <span className="text-slate-700 select-none shrink-0 w-16 text-right">{line.timestamp}</span>
            <pre className={`flex-1 whitespace-pre-wrap break-all ${LEVEL_CLASS[line.level] ?? "text-slate-400"}`}>
              {line.output}
            </pre>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input row */}
      <div className="flex-shrink-0 flex items-center gap-2 px-3 py-2.5 border-t border-slate-800/60 bg-[#0a0a12]">
        <span className="text-emerald-500 shrink-0 select-none">ROOT@ORG:~#</span>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => { setInput(e.target.value); setHistIdx(-1); }}
          onKeyDown={handleKeyDown}
          placeholder={connected ? "type a command… (Tab to complete, ↑↓ for history)" : "connecting…"}
          disabled={!connected}
          spellCheck={false}
          autoComplete="off"
          className="flex-1 bg-transparent border-none outline-none text-white placeholder:text-slate-700
                     disabled:opacity-40 caret-emerald-400"
        />
        <button
          onClick={sendCmd}
          disabled={!connected || !input.trim()}
          className="text-[9px] tracking-widest text-slate-600 hover:text-emerald-400 disabled:opacity-20 px-2"
        >
          ⏎
        </button>
      </div>
    </div>
  );
}
