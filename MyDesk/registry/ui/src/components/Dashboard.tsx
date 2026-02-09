import React, { useEffect, useState, useCallback } from 'react';
import { api, type Agent } from '../lib/api';
import { toast } from 'sonner';
import { Trash2, Globe, Monitor, Clock, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface DashboardProps {
    password: string;
    onLogout: () => void;
}

export function Dashboard({ password, onLogout }: DashboardProps) {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchAgents = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.discover(password);
            // Sort: Active first, then by Last Updated
            const sorted = data.sort((a, b) => {
                if (a.active === b.active) {
                    return new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime();
                }
                return a.active ? -1 : 1;
            });
            setAgents(sorted);
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            toast.error("Failed to fetch agents: " + msg);
            if (msg.includes("Access Denied")) {
                onLogout();
            }
        } finally {
            setLoading(false);
        }
    }, [password, onLogout]);

    useEffect(() => {
        fetchAgents();
        // Auto-refresh every 60s
        const interval = setInterval(fetchAgents, 60000);
        return () => clearInterval(interval);
    }, [fetchAgents]);

    const handleCopy = (url: string) => {
        navigator.clipboard.writeText(url)
            .then(() => toast.success("Copied to clipboard!"))
            .catch((err) => {
                console.error("Failed to copy:", err);
                toast.error("Failed to copy to clipboard");
            });
    };

    const handleDelete = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this agent?")) return;
        
        try {
            await api.delete(id, password);
            toast.success("Agent deleted");
            fetchAgents();
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            toast.error("Failed to delete: " + msg);
        }
    };

    return (
        <div className="min-h-screen bg-black text-white p-8">
            <header className="max-w-7xl mx-auto flex items-center justify-between mb-12">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
                        <Monitor className="w-5 h-5 text-black" />
                    </div>
                    <h1 className="text-xl font-bold">MyDesk Registry</h1>
                </div>
                <div className="flex items-center gap-4">
                    <button 
                        onClick={() => fetchAgents()} 
                        className="p-2 text-zinc-400 hover:text-white hover:bg-white/10 rounded-full transition-all active:scale-95"
                        title="Refresh"
                    >
                        <RefreshCw className={clsx("w-5 h-5", loading && "animate-spin")} />
                    </button>
                    <button 
                        onClick={onLogout} 
                        className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-lg transition-all border border-transparent hover:border-zinc-800"
                    >
                        Logout
                    </button>
                </div>
            </header>

            <main className="max-w-7xl mx-auto">
                {agents.length === 0 && !loading ? (
                    <div className="text-center py-20 text-zinc-500">
                        <p>No agents found. Start an agent to appear here.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {agents.map((agent) => (
                            <div 
                                key={agent.id}
                                onClick={() => handleCopy(agent.url)}
                                className={twMerge(
                                    "group relative p-6 rounded-xl border transition-all cursor-pointer hover:-translate-y-1 hover:shadow-xl",
                                    agent.active 
                                        ? "bg-zinc-900 border-zinc-800 hover:border-green-500/50 hover:shadow-green-900/20" 
                                        : "bg-black border-zinc-900 opacity-60 grayscale hover:opacity-100 hover:grayscale-0"
                                )}
                            >
                                {/* Status Indicator */}
                                <div className={clsx(
                                    "absolute top-4 right-4 w-2 h-2 rounded-full",
                                    agent.active ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" : "bg-zinc-700"
                                )} />

                                <div className="space-y-4">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-zinc-950 border border-zinc-800 rounded-lg">
                                            <Monitor className="w-5 h-5 text-zinc-400" />
                                        </div>
                                        <div>
                                            <h3 className="font-medium text-zinc-200">{agent.username || "Unknown User"}</h3>
                                            <p className="text-xs text-zinc-500 font-mono truncate max-w-[150px]">{agent.id}</p>
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 text-xs text-zinc-400">
                                            <Globe className="w-3 h-3" />
                                            <span className="truncate max-w-full">{agent.url}</span>
                                        </div>
                                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                                            <Clock className="w-3 h-3" />
                                            <span>{new Date(agent.last_updated).toLocaleString()}</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="absolute top-4 right-10 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                                    <button 
                                        onClick={(e) => handleDelete(agent.id, e)}
                                        className="p-1.5 bg-red-500/10 text-red-500 rounded hover:bg-red-500 hover:text-white transition-colors"
                                        title="Delete"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                                
                                <div className="absolute inset-0 border-2 border-transparent group-hover:border-white/5 rounded-xl pointer-events-none" />
                            </div>
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
}
