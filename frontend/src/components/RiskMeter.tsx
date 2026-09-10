import { motion } from "framer-motion";

const LEVEL_COLORS: Record<string, string> = {
  LOW: "#34D399",
  MEDIUM: "#FBBF24",
  HIGH: "#F87171",
  CRITICAL: "#EF4444",
};

export default function RiskMeter({
  score,
  level,
  size = 190,
}: {
  score: number;
  level: string;
  size?: number;
}) {
  const r = size / 2 - 14;
  const circ = Math.PI * r; // half circle length
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color =
    level === "CRITICAL" ? "#EF4444" :
    level === "HIGH" ? "#F87171" :
    level === "MEDIUM" ? "#FBBF24" : "#34D399";

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.62} viewBox={`0 0 ${size} ${size * 0.62}`}>
        <path
          d={`M ${size / 2 - r} ${size * 0.55} A ${r} ${r} 0 0 1 ${size / 2 + r} ${size * 0.55}`}
          fill="none"
          stroke="#1B2740"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <motion.path
          d={`M ${size / 2 - r} ${size * 0.55} A ${r} ${r} 0 0 1 ${size / 2 + r} ${size * 0.55}`}
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ * (1 - pct) }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          strokeDasharray={circ}
        />
        <text
          x={size / 2}
          y={size * 0.42}
          textAnchor="middle"
          className="fill-slate-100 font-bold"
          style={{ fontSize: size * 0.24 }}
        >
          {score}
        </text>
        <text
          x={size / 2}
          y={size * 0.55}
          className="fill-slate-500"
          style={{ fontSize: size * 0.07 }}
        >
          / 100
        </text>
      </svg>
      <div
        className="badge mt-1 text-sm px-3 py-1"
        style={{
          color,
          background: `${color}1A`,
          border: `1px solid ${color}55`,
        }}
      >
        {level} RISK
      </div>
    </div>
  );
}