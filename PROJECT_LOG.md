# Project Log

- 2026-05-21: Added frontend scaffolding, Vite setup, and initial dashboard UI components for the log analyzer.
- 2026-05-21: Tweaked anomaly display and chart axis labels for cleaner UX.
- 2026-05-21: Deduplicated repeated time labels on short traffic windows.
- 2026-05-21: Reworked traffic chart with area fill, gridlines, and y-axis ticks for readability.
- 2026-05-21: Bucketed traffic chart into 5/10-minute intervals and styled error series as dashed line.
- 2026-05-21: Fixed backend request bucketing and softened chart fill for clearer series separation.
- 2026-05-21: Switched chart gradient stops to explicit amber hex values and restored fill opacity.
- 2026-05-21: Removed SVG stretching on the traffic chart by preserving aspect ratio and keeping width-based sizing.
- 2026-05-21: Restored full-width chart stretching and widened SVG coordinate space for smoother curves.
- 2026-05-21: Brought y-axis labels above the chart with padding and a text halo for readability.
- 2026-05-21: Moved y-axis labels into a left column beside the chart to eliminate overlap.
- 2026-05-21: Tuned the sample log generator for realistic status, latency, and response-time distributions.
- 2026-05-21: Fixed parser anomaly counting so alternate response-time formats are tracked correctly.
- 2026-05-22: Added robust latency metrics (capped mean, median) and negative-latency tracking.
- 2026-05-22: Improved parsing with quoted-field tokenization and stack-trace continuation handling.
