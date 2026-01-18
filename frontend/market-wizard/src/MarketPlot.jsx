import React, { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import Papa from "papaparse";

const FILES = {
  "Normal Market": "/data/training_data_normal_market.csv",
  "Stressed Market": "/data/training_data_stressed_market.csv",
  "HFT Dominated": "/data/training_data_hft_dominated.csv",
  "Flash Crash": "/data/training_data_flash_crash.csv",
  "Mini Flash Crash": "/data/training_data_mini_flash_crash.csv",
};

const DESCRIPTIONS = {
  "Normal Market":
    "Stable bid-ask spread and smooth price movement. Market makers can quote tightly with low inventory risk.",

  "Stressed Market":
    "Volatility is elevated and spreads widen as liquidity providers reduce exposure. Inventory risk increases.",

  "HFT Dominated":
    "Extremely tight spreads and rapid price oscillations driven by high-speed trading competition.",

  "Flash Crash":
    "Sudden liquidity vacuum with violent price drops and spread explosions caused by forced selling cascades.",

  "Mini Flash Crash":
    "Short-lived liquidity shock with rapid spread widening and quick partial recovery.",
};

export default function MarketPlot({ market }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    setData(null); // reset on switch

    fetch(FILES[market])
      .then((res) => res.text())
      .then((csv) => {
        Papa.parse(csv, {
          header: true,
          dynamicTyping: true,
          complete: (results) => {
            const clean = results.data.filter(
              (r) => r.bid > 0 && r.ask > 0 && r.mid > 0
            );
            setData(clean);
          },
        });
      });
  }, [market]);    

  return (
    !data? 
    <Plot
      layout={{
        title: {
          text: "LOADING <br><sub style='font-size:12px;color:#aaa'>" + DESCRIPTIONS[market] +  "</sub>",
        },
        xaxis: { title: "Step" },
        yaxis: { title: "Price" },
        legend: { orientation: "h" },
      }}
      style={{ width: "100%", height: "100%" }}
      useResizeHandler
    /> 
    : 
    <Plot
      data={[
        {
          x: data.map((r) => r.step),
          y: data.map((r) => r.mid),
          type: "scatter",
          mode: "lines",
          name: "Mid",
        },
        {
          x: data.map((r) => r.step),
          y: data.map((r) => r.bid),
          type: "scatter",
          mode: "lines",
          name: "Bid",
          opacity: 0.5,
        },
        {
          x: data.map((r) => r.step),
          y: data.map((r) => r.ask),
          type: "scatter",
          mode: "lines",
          name: "Ask",
          opacity: 0.5,
        },
      ]}
      layout={{
        title: {
          text: market + "<br><sub style='font-size:12px;color:#aaa'>" + DESCRIPTIONS[market] +  "</sub>",

        },
        xaxis: { title: "Step" },
        yaxis: { title: "Price" },
        legend: { orientation: "h" },
      }}
      style={{ width: "100%", height: "100%" }}
      useResizeHandler
    />
  );
}
