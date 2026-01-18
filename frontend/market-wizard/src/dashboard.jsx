import { useState } from "react";
import "./dashboard.css";
import MarketPlot from "./MarketPlot";

const graphs = [
  "Normal Market",
  "Stressed Market",
  "HFT Dominated",
  "Flash Crash",
  "Mini Flash Crash",
];

export default function Dashboard() {
  const [activeGraph, setActiveGraph] = useState("Normal Market");

  return (
    <div className="dashboard">
      <aside className="sidebar">
        <div className="sidebar-title"></div>
        {graphs.map((label) => (
          <button
            key={label}
            onClick={() => setActiveGraph(label)}
            className={`tab ${activeGraph === label ? "active" : ""}`}
          >
            {label}
          </button>
        ))}
      </aside>

      <main className="content">
        <div className="graph-container">
          <MarketPlot market={activeGraph} />
        </div>
      </main>
    </div>
  );
}
