import React, { useState } from "react";
import Plot from "react-plotly.js";
import Papa from "papaparse";

function CSVPlot() {
  const [data, setData] = useState([]);
  const [fileName, setFileName] = useState("");

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setFileName(file.name);

    Papa.parse(file, {
      header: true, // read first row as keys
      dynamicTyping: true, // convert numbers automatically
      complete: function (results) {
        setData(results.data);
      },
    });
  };

  const step = data.map((r) => r.step);
  const bid = data.map((r) => r.bid);
  const ask = data.map((r) => r.ask);
  const mid = data.map((r) => r.mid);
  const spread = data.map((r) => r.spread);

  return (
    <div>
      <h2>CSV Viewer: {fileName}</h2>
      <input type="file" accept=".csv" onChange={handleFileChange} />
      {data.length > 0 && (
        <>
          <Plot
            data={[
              { x: step, y: bid, type: "scatter", mode: "lines", name: "bid", line: { color: "green" } },
              { x: step, y: ask, type: "scatter", mode: "lines", name: "ask", line: { color: "red" } },
              { x: step, y: mid, type: "scatter", mode: "lines", name: "mid", line: { color: "blue" } },
              { x: step, y: spread, type: "scatter", mode: "lines", name: "spread", line: { color: "orange", dash: "dot" } },
            ]}
            layout={{
              title: "Prices & Spread vs Step",
              xaxis: { title: "Step" },
              yaxis: { title: "Price / Spread" },
            }}
            style={{ width: "100%", height: "400px" }}
          />
        </>
      )}
    </div>
  );
}

export default CSVPlot;
