"use client";

import React, { useState } from 'react';
import { Check, Shield, Crosshair, Terminal } from 'lucide-react';
import { clsx } from 'clsx';

export default function TacticalStepper() {
    const [step, setStep] = useState(1);
    
    const steps = [
        { id: 1, title: 'Define Target', icon: Crosshair, desc: 'Select asset or IP range.' },
        { id: 2, title: 'Deploy Guardrails', icon: Shield, desc: 'Configure ABAC constraints.' },
        { id: 3, title: 'Execute Payload', icon: Terminal, desc: 'Launch autonomous agent.' }
    ];

    return (
        <div className="w-full max-w-3xl mx-auto p-6 bg-surface border border-surface-border rounded-xl shadow-lg font-mono">
            <h2 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-surface-border pb-2">
                Guided Tactical Workflow
            </h2>
            
            <div className="flex items-center justify-between relative mb-8">
                {/* Connecting Line */}
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-0.5 bg-surface-border z-0" />
                
                {steps.map((s) => {
                    const isActive = step === s.id;
                    const isCompleted = step > s.id;
                    
                    return (
                        <div key={s.id} className="relative z-10 flex flex-col items-center bg-surface px-4">
                            <div className={clsx(
                                "w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300",
                                isCompleted ? "bg-primary border-primary text-black shadow-[0_0_15px_rgba(0,229,255,0.5)]" : 
                                isActive ? "bg-primary/20 border-primary text-primary shadow-[0_0_15px_rgba(0,229,255,0.3)]" : 
                                "bg-surface border-surface-border text-muted"
                            )}>
                                {isCompleted ? <Check size={18} /> : <s.icon size={18} />}
                            </div>
                            <div className="mt-3 text-center">
                                <p className={clsx("text-xs font-bold uppercase", isActive || isCompleted ? "text-primary" : "text-muted")}>
                                    {s.title}
                                </p>
                                <p className="text-[10px] text-muted mt-1 max-w-[100px]">{s.desc}</p>
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="bg-black/50 border border-surface-border rounded p-6 min-h-[200px] flex items-center justify-center">
                <p className="text-muted text-sm uppercase tracking-wide animate-pulse">
                    [ Waiting for Operator Input: Step {step} ]
                </p>
            </div>

            <div className="mt-6 flex justify-between">
                <button 
                    disabled={step === 1} 
                    onClick={() => setStep(step - 1)}
                    className="px-4 py-2 text-xs font-bold uppercase border border-surface-border text-muted hover:text-white disabled:opacity-50 transition-colors"
                >
                    Abort / Back
                </button>
                <button 
                    disabled={step === 3} 
                    onClick={() => setStep(step + 1)}
                    className="px-6 py-2 text-xs font-bold uppercase bg-primary text-black shadow-[0_0_15px_rgba(0,229,255,0.3)] hover:shadow-[0_0_20px_rgba(0,229,255,0.6)] disabled:opacity-50 transition-all"
                >
                    {step === 3 ? 'Executing...' : 'Proceed to Next Phase'}
                </button>
            </div>
        </div>
    );
}
