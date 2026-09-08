'use client';

interface RiskMeterProps {
    score: number;
}

export default function RiskMeter({ score }: RiskMeterProps) {
    // Determine color based on score
    let color = "text-success";
    if (score > 60) color = "text-warning";
    if (score > 80) color = "text-alert";

    const radius = 40;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;

    return (
        <div className="relative flex items-center justify-center w-32 h-32">
            {/* Background Circle */}
            <svg className="w-full h-full transform -rotate-90">
                <circle
                    className="text-gray-800"
                    strokeWidth="8"
                    stroke="currentColor"
                    fill="transparent"
                    r={radius}
                    cx="64"
                    cy="64"
                />
                {/* Progress Circle */}
                <circle
                    className={`${color} transition-all duration-1000 ease-out`}
                    strokeWidth="8"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="transparent"
                    r={radius}
                    cx="64"
                    cy="64"
                />
            </svg>
            <div className="absolute flex flex-col items-center">
                <span className={`text-3xl font-bold font-mono ${color}`}>{score}</span>
                <span className="text-[10px] text-gray-500 uppercase tracking-widest">RISK</span>
            </div>
        </div>
    );
}
