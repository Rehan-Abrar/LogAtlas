function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-US').format(value);
}

export default function ErrorTable({ data, hasData }) {
  if (!hasData) {
    return (
      <div className="panel">
        <div className="empty">Upload a log file to surface error hot-spots.</div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="chart-block">
        <div className="chart-block__header">
          <div>
            <h3>Erroring IPs</h3>
            <p>Sources with the highest proportion of 4xx/5xx traffic.</p>
          </div>
        </div>
        <div className="table">
          <div className="table__row table__row--head">
            <span>IP address</span>
            <span>Errors</span>
            <span>Total</span>
            <span>Rate</span>
          </div>
          {(data.top_error_ips || []).map((item) => (
            <div className="table__row" key={item.ip}>
              <span>{item.ip}</span>
              <span>{formatNumber(item.error_count)}</span>
              <span>{formatNumber(item.total_requests)}</span>
              <span>{item.error_rate}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className="chart-block">
        <div className="chart-block__header">
          <div>
            <h3>Malformed samples</h3>
            <p>Example lines that could not be parsed, preserved for forensics.</p>
          </div>
        </div>
        <div className="samples">
          {(data.malformed_samples || []).length === 0 && (
            <div className="empty">No malformed lines captured.</div>
          )}
          {(data.malformed_samples || []).map((line, idx) => (
            <div className="sample" key={`${line}-${idx}`}>
              <span className="sample__index">{idx + 1}</span>
              <span className="sample__text">{line}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
