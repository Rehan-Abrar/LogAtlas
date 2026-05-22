import { useRef, useState } from 'react';

import Charts from './Charts';
import ErrorTable from './ErrorTable';

const defaultMeta = {
  filename: 'No file selected',
  size: '—',
  lines: '—',
  parsed: '—',
  malformed: '—',
};

function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-US').format(value);
}

function formatPercent(value) {
  if (value === null || value === undefined) return '—';
  return `${value}%`;
}

function formatDuration(value) {
  if (value === null || value === undefined) return '—';
  return `${value}s`;
}

function formatMilliseconds(value) {
  if (value === null || value === undefined) return '—';
  return `${value} ms`;
}

function formatFileSize(kb) {
  if (kb === null || kb === undefined) return '—';
  if (kb < 1024) return `${kb} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

export default function Dashboard({
  data,
  busy,
  error,
  hasData,
  onAnalyzeStart,
  onAnalyzeSuccess,
  onAnalyzeError,
}) {
  const inputRef = useRef(null);
  const [fileMeta, setFileMeta] = useState(defaultMeta);
  const [dragActive, setDragActive] = useState(false);

  const summary = data?.summary;

  const handleFile = async (file) => {
    if (!file) return;
    onAnalyzeStart();
    setFileMeta((prev) => ({
      ...prev,
      filename: file.name,
      size: formatFileSize(Math.round(file.size / 1024)),
    }));

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.detail || 'Upload failed.');
      }

      const payload = await response.json();
      onAnalyzeSuccess(payload);
      setFileMeta({
        filename: payload.filename || file.name,
        size: formatFileSize(payload.file_size_kb),
        lines: formatNumber(payload.summary?.total_lines),
        parsed: formatNumber(payload.summary?.total_requests),
        malformed: formatNumber(payload.summary?.malformed_count),
      });
    } catch (err) {
      onAnalyzeError(err.message || 'Unexpected error while analyzing.');
    }
  };

  const handleInput = (event) => {
    const file = event.target.files?.[0];
    void handleFile(file);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    void handleFile(file);
  };

  const anomalies = Object.entries(summary?.format_anomalies || {}).filter(
    ([key]) => key !== 'json_lines',
  );

  return (
    <section className="dashboard">
      <div className="hero">
        <div className="hero__copy">
          <span className="eyebrow">Operational intelligence</span>
          <h1>Log Atlas turns noisy traffic into a calm signal.</h1>
          <p className="hero__lede">
            Drop in a log file and get an editorial dashboard that highlights failures, latency spikes,
            and format anomalies. Built for on-call moments where clarity matters more than perfection.
          </p>
          <div className="hero__points">
            <div className="hero__point">
              <div className="hero__point-label">Latency</div>
              <div className="hero__point-value">Top 10 slowest paths surfaced.</div>
            </div>
            <div className="hero__point">
              <div className="hero__point-label">Errors</div>
              <div className="hero__point-value">IP hot-spots ranked by impact.</div>
            </div>
            <div className="hero__point">
              <div className="hero__point-label">Anomalies</div>
              <div className="hero__point-value">Malformed lines never ignored.</div>
            </div>
          </div>
        </div>

        <div className="hero__action">
          <div
            className={`dropzone ${dragActive ? 'is-active' : ''}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
          >
            <input
              className="file-input"
              type="file"
              accept=".log,.txt"
              ref={inputRef}
              onChange={handleInput}
            />
            <div className="dropzone__art">
              <div className="signal-orb" />
              <div className="dropzone__title">Drop your log file</div>
            </div>
            <div className="dropzone__hint">
              We will parse multiple formats, surface anomalies, and keep the raw evidence intact.
            </div>
            <div className="dropzone__meta">
              <div className="pill">ISO, epoch, and named date formats</div>
              <div className="pill">ms / s / bare timing values</div>
              <div className="pill">JSON and mixed formats</div>
            </div>
          </div>

          <div className="upload-controls">
            <div className="field-row">
              <button
                className="button button--primary"
                type="button"
                onClick={() => inputRef.current?.click()}
                disabled={busy}
              >
                {busy ? 'Analyzing…' : 'Choose log file'}
              </button>
              <button
                className="button button--ghost"
                type="button"
                onClick={() => {
                  setFileMeta(defaultMeta);
                  onAnalyzeSuccess({
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
                  });
                }}
                disabled={busy}
              >
                Reset dashboard
              </button>
            </div>

            <div className="selection">
              <div className="selection__label">File snapshot</div>
              <div className="selection__value">{fileMeta.filename}</div>
              <div className="selection__value">{fileMeta.size}</div>
              <div className="selection__value">Lines: {fileMeta.lines}</div>
              <div className="selection__value">Parsed: {fileMeta.parsed}</div>
              <div className="selection__value">Malformed: {fileMeta.malformed}</div>
            </div>
          </div>

          {error && (
            <div className="flash" role="alert">
              <div className="flash__title">Upload failed</div>
              <div className="flash__copy">{error}</div>
            </div>
          )}

          {hasData && !error && (
            <div className="flash flash--success">
              <div className="flash__title">Analysis complete</div>
              <div className="flash__copy">Scroll for status breakdowns, hotspots, and anomalies.</div>
            </div>
          )}
        </div>
      </div>

      <div className="dashboard__header">
        <div className="dashboard__title">
          <h2>Operational summary</h2>
          <p>
            A compact readout for the busiest slices of your log. Use this to spot error rates,
            response-time spikes, and parsing health before diving into raw traces.
          </p>
        </div>
        <div className="dashboard__meta">
          <div className="pill">{summary?.time_range_start || 'No time window yet'}</div>
          <div className="pill">{summary?.time_range_end || 'Waiting for log data'}</div>
          <div className="pill">Range {formatDuration(summary?.duration_seconds)}</div>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi">
          <div className="kpi__label">Total requests</div>
          <div className="kpi__value">{formatNumber(summary?.total_requests)}</div>
          <div className="kpi__hint">Parsed from {formatNumber(summary?.total_lines)} lines.</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Parse success</div>
          <div className="kpi__value">{formatPercent(summary?.parse_success_rate)}</div>
          <div className="kpi__hint">Malformed lines kept visible, never dropped.</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Error rate</div>
          <div className="kpi__value">{formatPercent(summary?.error_rate)}</div>
          <div className="kpi__hint">Requests with 4xx/5xx responses.</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Avg latency</div>
          <div className="kpi__value">{formatMilliseconds(summary?.avg_response_ms)}</div>
          <div className="kpi__hint">Mean response time across parsed requests.</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">P95 latency</div>
          <div className="kpi__value">{formatMilliseconds(summary?.p95_response_ms)}</div>
          <div className="kpi__hint">Tail latency for 95th percentile.</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">P99 latency</div>
          <div className="kpi__value">{formatMilliseconds(summary?.p99_response_ms)}</div>
          <div className="kpi__hint">Worst-case latency segment.</div>
        </div>
      </div>

      <div className="dashboard__layout">
        <Charts data={data} hasData={hasData} />
        <ErrorTable data={data} hasData={hasData} />
      </div>

      <div className="panel anomaly-panel">
        <div className="anomaly-panel__head">
          <div>
            <h3>Format anomalies</h3>
            <p>Places where the log format drifted, malformed, or shifted into JSON.</p>
          </div>
          <div className="pill">JSON lines {formatNumber(summary?.json_line_count)}</div>
        </div>
        <div className="anomaly-grid">
          {anomalies.map(([key, value]) => (
            <div className="anomaly" key={key}>
              <div>
                <div className="anomaly__name">{key.replace(/_/g, ' ')}</div>
                <div className="anomaly__count">{formatNumber(value)}</div>
              </div>
              <div className="anomaly__bar">
                <span style={{ width: `${Math.min((value / (summary?.total_lines || 1)) * 100, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
