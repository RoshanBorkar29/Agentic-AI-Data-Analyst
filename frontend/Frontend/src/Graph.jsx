import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Label,
} from "recharts";

function Graph({ chart }) {
  if (!chart || chart.type === "none") {
    return (
      <div className="chart-empty">
        NO visualization avaliable.
      </div>
    );
  }

  const data = chart.data || [];

  if (!data.length) {
    return (
      <div className="chart-empty">
        No chart data available.
      </div>
    );
  }

  if (chart.type === "bar") {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <BarChart
          data={data}
          margin={{ top: 10, right: 20, left: 30, bottom: 25 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey={chart.x_axis}
            tick={{ fill: "#94a3b8" }}
          >
            <Label value={chart.x_axis} position="insideBottom" offset={-15} />
          </XAxis>
          <YAxis width={80} tick={{ fill: "#94a3b8" }}>
            <Label value={chart.y_axis} angle={-90} position="insideLeft" />
          </YAxis>
          <Tooltip />
          <Bar dataKey={chart.y_axis} fill="#38bdf8" />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (chart.type === "line") {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart
          data={data}
          margin={{ top: 10, right: 20, left: 30, bottom: 25 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={chart.x_axis}>
            <Label value={chart.x_axis} position="insideBottom" offset={-15} />
          </XAxis>
          <YAxis>
            <Label value={chart.y_axis} angle={-90} position="insideLeft" />
          </YAxis>
          <Tooltip />
          <Line type="monotone" dataKey={chart.y_axis} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (chart.type === "pie") {
    return (
      <ResponsiveContainer width="100%" height={500}>
        <PieChart>
          <Pie
            data={data}
            dataKey={chart.y_axis}
            nameKey={chart.x_axis}
            cx="50%"
            cy="50%"
            outerRadius={140}
            label
          >
            {data.map((_, index) => (
              <Cell
                key={index}
                fill={["#38bdf8", "#a78bfa", "#34d399", "#f59e0b"][index % 4]}
              />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (chart.type === "scatter") {
    return (
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 10, right: 20, left: 30, bottom: 25 }}>
          <CartesianGrid />
          <XAxis
            type="number"
            dataKey={chart.x_axis}
            name={chart.x_axis}
          >
            <Label value={chart.x_axis} position="insideBottom" offset={-15} />
          </XAxis>
          <YAxis
            type="number"
            dataKey={chart.y_axis}
            name={chart.y_axis}
          >
            <Label value={chart.y_axis} angle={-90} position="insideLeft" />
          </YAxis>
          <Tooltip />
          <Scatter data={data} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  if (chart.type === "histogram") {
    return (
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={data} margin={{ top: 10, right: 20, left: 30, bottom: 25 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={chart.x_axis}>
            <Label value={chart.x_axis} position="insideBottom" offset={-15} />
          </XAxis>
          <YAxis>
            <Label value={chart.y_axis} angle={-90} position="insideLeft" />
          </YAxis>
          <Tooltip />
          <Bar dataKey={chart.y_axis} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <div className="chart-empty">
      Chart type not supported yet.
    </div>
  );
}

export default Graph;
