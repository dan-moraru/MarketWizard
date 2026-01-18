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

        {/* INSIGHTS SECTION */}
        <div className="insights">
          <h2>Project Insights & Findings</h2>

          <p>
            This project evolved through deep interaction with live market microstructure.
            Rather than treating the simulator as a black box, we studied its behavior,
            visualized its data, and adapted our system accordingly.
          </p>

          <hr />

          <h3>System Design & Features</h3>
          <ul>
            <li>Real-time ingestion of bid/ask market data</li>
            <li>Microstructure feature engineering</li>
            <li>Market regime classification using XGBoost</li>
            <li>
              Supports multiple regimes:
              <ul>
                <li>Normal market</li>
                <li>Stressed market</li>
                <li>HFT-dominated market</li>
                <li>Flash events</li>
              </ul>
            </li>
          </ul>

          <p>
            We use a multi-class XGBoost classifier trained on engineered microstructure
            features instead of raw prices.
          </p>

          <p>
            Key design principles:
          </p>
          <ul>
            <li>Relative features instead of absolute prices</li>
            <li>Rolling statistical indicators</li>
            <li>Regime classification instead of price prediction</li>
            <li>Emphasis on stability and interpretability</li>
          </ul>

          <hr />

          <h3>Why We Logged and Visualized the Data</h3>
          <p>
            We first logged market data in order to visualize it and understand what we
            were working with. Raw price streams were too noisy to reason about directly.
          </p>

          <p>
            Visual inspection revealed that each market regime exhibits a distinct
            microstructure signature — spread behavior, volatility, and liquidity dynamics
            differ far more than raw prices alone suggest.
          </p>

          <p>
            The visible gaps in the charts correspond to rows containing zero values, which
            were removed during data cleaning.
          </p>

          <hr />

          <h3>Data Quality Issues: Zero-Value Rows</h3>
          <p>
            We observed frequent rows where bid, ask, and mid prices were recorded as zero.
            These segments appear to be either intentional obstacles or artifacts of the
            synthetic data generator.
          </p>

          <p>
            These invalid rows were filtered to prevent corrupting statistical features
            and model training.
          </p>

          <hr />

          <h3>Normal Market Structure Anomaly</h3>
          <p>
            In the normal market regime, prices barely move, yet extremely consistent profits
            were achievable. Investigation showed that the market-making bots operate on a
            fixed grid of approximately $0.25.
          </p>

          <p>
            By placing bids and asks slightly inside this grid, we effectively gained a
            monopoly on liquidity provision, allowing repeated risk-free fills between
            gridlocked bots.
          </p>

          <p>
            The dataset itself was nearly constant across time, except for one column that
            revealed a clear mean-reversion opportunity in the spread.
          </p>

          <hr />

          <h3>Bug 1 — Crossed-Spread Instant Fill Exploit</h3>
          <p>
            We discovered that the simulator fills BUY orders placed anywhere inside the
            bid-ask spread as long as they are above the best bid. Likewise, SELL orders
            inside the spread fill as long as they are below the best ask.
          </p>

          <p>
            This enables an unintended arbitrage loop:
          </p>
          <ul>
            <li>Buy at bid + 0.01</li>
            <li>Sell at ask - 0.01</li>
            <li>Both orders fill instantly</li>
          </ul>

          <p>
            This produces infinite risk-free profit even in the normal market regime where
            prices are nearly static.
          </p>

          <p>
            In real exchanges, this is impossible:
          </p>
          <ul>
            <li>BUY orders only execute at the best ask or higher</li>
            <li>SELL orders only execute at the best bid or lower</li>
          </ul>

          <p>
            This bug effectively removes the bid-ask spread as a trading cost, violating a
            fundamental principle of market microstructure.
          </p>

          <hr />

          <h3>Bug 2 — No Order Cancellation Mechanism</h3>
          <p>
            The exchange provides no mechanism to cancel resting limit orders.
          </p>

          <p>
            As a result:
          </p>
          <ul>
            <li>Orders placed far from the market may never fill</li>
            <li>These “zombie orders” accumulate silently</li>
            <li>The system eventually hits the 50 open order limit and disconnects</li>
          </ul>

          <p>
            This forced us to implement internal risk controls and order throttling similar
            to real-world trading infrastructure.
          </p>

          <hr />

          <h3>Key Lesson</h3>
          <p>
            We learned that understanding market structure is more important than predicting
            prices. Strategies must adapt to regime changes before losses occur, not after.
          </p>
        </div>

      </main>
    </div>
  );
}
