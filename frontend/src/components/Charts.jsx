const tone = {
  '2xx': 'chart-chip chart-chip--teal',
  '3xx': 'chart-chip chart-chip--amber',
  '4xx': 'chart-chip chart-chip--rust',
  '5xx': 'chart-chip chart-chip--lime',
  unknown: 'chart-chip',
};

function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-US').format(value);
}

function chartMax(list, accessor) {
  return Math.max(1, ...list.map(accessor));
}

function buildBuckets(series, summary) {
  if (!series.length || !summary?.time_range_start || !summary?.time_range_end) {
    return { buckets: series, intervalMinutes: null };
  }

  const start = new Date(summary.time_range_start);
  const end = new Date(summary.time_range_end);
  const totalMs = Math.max(end.getTime() - start.getTime(), 1);
  const totalMinutes = totalMs / 60000;
  const intervalMinutes = totalMinutes >= 120 ? 10 : 5;
  const intervalMs = intervalMinutes * 60 * 1000;

  const bucketPoints = series.map((point, index) => {
    const ratio = series.length === 1 ? 0 : index / (series.length - 1);
    const ts = new Date(start.getTime() + ratio * totalMs);
    return { ...point, ts };
  });

  const grouped = new Map();
  const bucketStart = Math.floor(start.getTime() / intervalMs) * intervalMs;
  const bucketEnd = Math.floor(end.getTime() / intervalMs) * intervalMs;

  bucketPoints.forEach((point) => {
    const bucket = Math.floor(point.ts.getTime() / intervalMs) * intervalMs;
    const existing = grouped.get(bucket) || { requests: 0, errors: 0 };
    grouped.set(bucket, {
      requests: existing.requests + (point.requests || 0),
      errors: existing.errors + (point.errors || 0),
    });
  });

  const formatter = new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const buckets = [];
  for (let t = bucketStart; t <= bucketEnd; t += intervalMs) {
    const slot = grouped.get(t) || { requests: 0, errors: 0 };
    buckets.push({
      time: formatter.format(new Date(t)),
      requests: slot.requests,
      errors: slot.errors,
    });
  }

  return { buckets, intervalMinutes };
}

function RequestsChart({ series, summary }) {
  if (!series.length) {
    return <div className="empty">Upload a log file to render traffic trends.</div>;
  }

  const { buckets, intervalMinutes } = buildBuckets(series, summary);
  const max = chartMax(buckets, (point) => point.requests);
  const plotTop = 8;
  const plotBottom = 12;
  const plotHeight = 100 - plotTop - plotBottom;

  const plotWidth = 1000;

  const pathFor = (accessor) => {
    const points = buckets.map((point, index) => {
      const x = buckets.length === 1 ? plotWidth / 2 : (index / Math.max(buckets.length - 1, 1)) * plotWidth;
      const y = plotTop + (1 - accessor(point) / max) * plotHeight;
      return { x, y };
    });
    const line = points.map((pt, idx) => `${idx === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`).join(' ');
    const area = `${line} L ${plotWidth} ${plotTop + plotHeight} L 0 ${plotTop + plotHeight} Z`;
    return { line, area };
  };

  const requestsPath = pathFor((point) => point.requests);
  const errorPath = pathFor((point) => point.errors);

  const axisLabels = buckets.map((point) => point.time);
  const axisStep = Math.max(1, Math.floor(axisLabels.length / 6));
  const trimmedAxis = axisLabels.filter((_, index) => index % axisStep === 0);

  const tickValues = [
    max,
    Math.round(max * 0.75),
    Math.round(max * 0.5),
    Math.round(max * 0.25),
    0,
  ];

  return (
    <div className="chart-block">
      <div className="chart-block__header">
        <div>
          <h3>Traffic over time</h3>
        </div>
        <div className="chart-legend">
          <span>Requests</span>
          <span>Errors (dashed)</span>
        </div>
      </div>
      <div className="chart-frame">
        <div className="chart-y">
          {tickValues.map((value) => (
            <span key={value}>{formatNumber(value)}</span>
          ))}
        </div>
        <div className="chart-svg-wrap">
          <svg viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="requestsFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.03" />
            </linearGradient>
          </defs>
          <g className="chart-grid">
            {tickValues.map((value, idx) => {
              const y = plotTop + (1 - value / max) * plotHeight;
              return <line key={idx} x1="0" x2={plotWidth} y1={y} y2={y} />;
            })}
          </g>
          <path className="chart-area" d={requestsPath.area} fill="url(#requestsFill)" opacity="0.25" />
          <path className="chart-line" d={requestsPath.line} />
          <path className="chart-line chart-line--muted" d={errorPath.line} />
          </svg>
        </div>
      </div>
      <div className="chart-axis" style={{ gridTemplateColumns: `repeat(${trimmedAxis.length}, minmax(0, 1fr))` }}>
        {trimmedAxis.map((label, index) => (
          <span key={`${label}-${index}`}>{label}</span>
        ))}
      </div>
    </div>
  );
}

function StatusBars({ data }) {
  if (!data.length) {
    return <div className="empty">Awaiting status-code distribution.</div>;
  }
  const max = chartMax(data, (item) => item.count);
  return (
    <div className="chart-block">
      <div className="chart-block__header">
        <div>
          <h3>Status class mix</h3>
          <p>Relative volume by 1xx–5xx class with an emphasis on failures.</p>
        </div>
      </div>
      <div className="status-bars">
        {data.map((item) => (
          <div key={item.class} className="status-bar">
            <div className="status-bar__label">
              <span className={tone[item.class] || tone.unknown}>{item.class}</span>
              <span>{formatNumber(item.count)}</span>
            </div>
            <div className="status-bar__track">
              <div
                className="status-bar__fill"
                style={{ width: `${(item.count / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopEndpoints({ data }) {
  if (!data.length) {
    return <div className="empty">No endpoints to rank yet.</div>;
  }
  return (
    <div className="chart-block">
      <div className="chart-block__header">
        <div>
          <h3>Slowest endpoints</h3>
          <p>Average and peak latency for the most expensive routes.</p>
        </div>
      </div>
      <div className="table">
        <div className="table__row table__row--head">
          <span>Endpoint</span>
          <span>Avg</span>
          <span>P95</span>
          <span>Max</span>
        </div>
        {data.map((item) => (
          <div className="table__row" key={item.endpoint}>
            <span>{item.endpoint}</span>
            <span>{item.avg_ms} ms</span>
            <span>{item.p95_ms} ms</span>
            <span>{item.max_ms} ms</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Charts({ data, hasData }) {
  if (!hasData) {
    return (
      <div className="panel">
        <div className="empty">Upload a log to unlock the analysis panels.</div>
      </div>
    );
  }

  return (
    <div className="panel">
      <RequestsChart series={data.requests_over_time || []} summary={data.summary} />
      <StatusBars data={data.status_distribution || []} />
      <TopEndpoints data={data.slowest_endpoints || []} />
    </div>
  );
}
