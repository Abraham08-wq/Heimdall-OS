import React from 'react';
import { clsx } from 'clsx';

interface TerminalOutputProps {
    output: string;
    loading: boolean;
}

const TerminalOutput: React.FC<TerminalOutputProps> = ({ output, loading }) => {
    return (
        <div className="flex-1 mt-4 rounded-md border border-gray-700 bg-black overflow-hidden flex flex-col shadow-inner">
            <div className="bg-[#2d2d2d] px-4 py-2 flex items-center justify-between border-b border-gray-700">
                <span className="text-sm font-mono text-gray-400">output.log</span>
                <span className={clsx(
                    "w-2 h-2 rounded-full",
                    loading ? "bg-yellow-500 animate-pulse" : "bg-green-500"
                )}></span>
            </div>
            <pre className="p-4 text-xs font-mono text-green-500 bg-black h-full overflow-auto whitespace-pre-wrap">
                {loading ? (
                    <span className="text-gray-500 animate-pulse">Running script in sandbox...&gt;</span>
                ) : (
                    output || <span className="text-gray-600">No output.</span>
                )}
            </pre>
        </div>
    );
};

export default TerminalOutput;
