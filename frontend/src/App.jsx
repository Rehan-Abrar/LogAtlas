import { useMemo, useState } from 'react';

import Dashboard from './components/Dashboard';

const emptyState = {
  summary: null,
  status_distribution: [],
  status_code_breakdown: [],
  slowest_endpoints: [],
  top_error_ips: [],
  requests_over_time: [],
  top_endpoints_by_volume: [],
  method_distribution: [],
  malformed_samples: [],
  filename: null,
  file_size_kb: null,
};

export default function App() {
  const [data, setData] = useState(emptyState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const hasData = useMemo(() => Boolean(data?.summary), [data]);

  return (
    <div className="app">
      <div className="app__bg-shape app__bg-shape--a" />
      <div className="app__bg-shape app__bg-shape--b" />
      <div className="app__bg-shape app__bg-shape--c" />

      <div className="shell">
        <div className="topbar">
          <div className="brand">
            <span className="brand__mark" />
            <span className="brand__name">Log Atlas</span>
          </div>
          <div className="topbar__status">
            {hasData ? 'Live signal extracted from your log file.' : 'Awaiting a log to analyze.'}
          </div>
        </div>

        <Dashboard
          data={data}
          busy={busy}
          error={error}
          hasData={hasData}
          onAnalyzeStart={() => {
            setBusy(true);
            setError(null);
          }}
          onAnalyzeSuccess={(payload) => {
            setData(payload);
            setBusy(false);
          }}
          onAnalyzeError={(message) => {
            setError(message);
            setBusy(false);
          }}
        />
      </div>
    </div>
  );
}
