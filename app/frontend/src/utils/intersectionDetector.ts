import { EnergyDataPoint, IntersectionPoint, SeriesConfig } from '../types/energy';

/**
 * Calculates mathematical line segment intersections between active series.
 */
export function findSeriesIntersections(
  data: EnergyDataPoint[],
  activeSeries: SeriesConfig[]
): IntersectionPoint[] {
  // Only find intersections if at least 2 series are visible
  const visibleSeries = activeSeries.filter((s) => s.visible && s.id !== 'upperBound' && s.id !== 'lowerBound');
  if (visibleSeries.length < 2 || data.length < 2) {
    return [];
  }

  const intersections: IntersectionPoint[] = [];

  // Compare every pair of visible series
  for (let i = 0; i < visibleSeries.length; i++) {
    for (let j = i + 1; j < visibleSeries.length; j++) {
      const s1 = visibleSeries[i];
      const s2 = visibleSeries[j];

      for (let idx = 0; idx < data.length - 1; idx++) {
        const pt1 = data[idx];
        const pt2 = data[idx + 1];

        const y1_s1 = pt1[s1.id] as number;
        const y2_s1 = pt2[s1.id] as number;
        const y1_s2 = pt1[s2.id] as number;
        const y2_s2 = pt2[s2.id] as number;

        const diff1 = y1_s1 - y1_s2;
        const diff2 = y2_s1 - y2_s2;

        // Check if sign of difference changes (indicating a cross)
        if (diff1 * diff2 <= 0 && (diff1 !== 0 || diff2 !== 0)) {
          // Linear interpolation ratio t in [0, 1]
          const denom = Math.abs(diff1) + Math.abs(diff2);
          const t = denom === 0 ? 0 : Math.abs(diff1) / denom;

          // Exact index position (can be fractional, e.g. 4.35)
          const exactXIndex = idx + t;

          // Exact interpolated price value
          const exactValue = y1_s1 + t * (y2_s1 - y1_s1);

          // Interpolated time label
          const hourLabel = t < 0.5 ? pt1.hour : pt2.hour;
          const dateLabel = pt1.date;

          intersections.push({
            id: `intersect-${s1.id}-${s2.id}-${idx}`,
            xIndex: parseFloat(exactXIndex.toFixed(2)),
            timestamp: `${pt1.date} ${pt1.hour}`,
            hourLabel: `${hourLabel} (T+${Math.round(t * 60)}dk)`,
            dateLabel,
            exactValue: parseFloat(exactValue.toFixed(2)),
            series1Id: s1.id,
            series1Name: s1.name,
            series1Color: s1.color,
            series2Id: s2.id,
            series2Name: s2.name,
            series2Color: s2.color,
            differenceBefore: parseFloat(Math.abs(diff1).toFixed(2)),
            differenceAfter: parseFloat(Math.abs(diff2).toFixed(2))
          });
        }
      }
    }
  }

  return intersections;
}
