import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { EnergyDataPoint, IntersectionPoint, SeriesConfig } from '../../types/energy';
import { Crosshair } from 'lucide-react';

interface MainChartProps {
  data: EnergyDataPoint[];
  seriesConfigs: SeriesConfig[];
  intersections: IntersectionPoint[];
  showIntersections: boolean;
  showConfidenceInterval: boolean;
  onIntersectionSelect?: (intersection: IntersectionPoint) => void;
}

export const MainChart: React.FC<MainChartProps> = ({
  data,
  seriesConfigs,
  intersections,
  showIntersections,
  showConfidenceInterval,
  onIntersectionSelect
}) => {
  const option = useMemo(() => {
    if (!data || data.length === 0) return {};

    const xAxisLabels = data.map((d) => `${d.date.slice(5)} ${d.hour}`);

    // Build ECharts series array
    const chartSeries: any[] = [];

    // Add confidence band if enabled
    if (showConfidenceInterval) {
      chartSeries.push({
        name: 'Güven Aralığı Alt',
        type: 'line',
        data: data.map((d) => d.lowerBound),
        lineStyle: { opacity: 0 },
        stack: 'confidence',
        symbol: 'none',
        silent: true
      });
      chartSeries.push({
        name: 'Güven Aralığı (%95)',
        type: 'line',
        data: data.map((d) => d.upperBound - d.lowerBound),
        lineStyle: { opacity: 0 },
        areaStyle: {
          color: 'rgba(148, 163, 184, 0.12)'
        },
        stack: 'confidence',
        symbol: 'none',
        silent: true
      });
    }

    // Add main data series based on visibility
    seriesConfigs.forEach((sc) => {
      if (!sc.visible) return;

      const seriesData = data.map((d) => d[sc.id] as number);

      const isArea = sc.chartType === 'area';
      const isSmooth = sc.chartType === 'smooth' || sc.chartType === 'area';
      const isBar = sc.chartType === 'bar';

      chartSeries.push({
        name: sc.name,
        type: isBar ? 'bar' : 'line',
        smooth: isSmooth,
        data: seriesData,
        symbol: 'circle',
        symbolSize: 5,
        showSymbol: false,
        itemStyle: {
          color: sc.color
        },
        lineStyle: {
          width: 2.5,
          color: sc.color
        },
        areaStyle: isArea
          ? {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: sc.color + '40' },
                  { offset: 1, color: sc.color + '05' }
                ]
              }
            }
          : undefined
      });
    });

    // Add Intersection Ping scatter series
    if (showIntersections && intersections.length > 0) {
      const pingData = intersections.map((it) => ({
        name: `Kesişim: ${it.series1Name} & ${it.series2Name}`,
        value: [it.xIndex, it.exactValue],
        intersectionObj: it
      }));

      chartSeries.push({
        name: 'Kesişim Pingleme',
        type: 'effectScatter',
        coordinateSystem: 'cartesian2d',
        data: pingData,
        symbolSize: 14,
        showEffectOn: 'render',
        rippleEffect: {
          brushType: 'stroke',
          scale: 4.5,
          period: 2
        },
        itemStyle: {
          color: '#f43f5e',
          shadowBlur: 15,
          shadowColor: '#f43f5e'
        },
        zlevel: 10
      });
    }

    return {
      backgroundColor: 'transparent',
      animation: true,
      animationDuration: 800,
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.3)',
        borderWidth: 1,
        textStyle: {
          color: '#f8fafc',
          fontSize: 12
        },
        axisPointer: {
          type: 'cross',
          crossStyle: {
            color: 'rgba(56, 189, 248, 0.5)'
          }
        },
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return '';
          const first = params[0];
          let res = `<div style="font-weight:700;margin-bottom:6px;color:#38bdf8;">🕒 Saat: ${first.name}</div>`;
          params.forEach((item: any) => {
            if (item.seriesName === 'Kesişim Pingleme' || item.seriesName.includes('Güven Aralığı Alt')) return;
            const val = typeof item.value === 'number' ? item.value.toLocaleString('tr-TR') : item.value;
            res += `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:3px 0;">
              <span>${item.marker} ${item.seriesName}:</span>
              <strong style="font-family:JetBrains Mono;">${val} ₺/MWh</strong>
            </div>`;
          });
          return res;
        }
      },
      legend: {
        show: true,
        top: '2%',
        right: '2%',
        textStyle: {
          color: '#94a3b8',
          fontSize: 12
        }
      },
      grid: {
        top: '12%',
        left: '4%',
        right: '4%',
        bottom: '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: xAxisLabels,
        boundaryGap: false,
        axisLine: {
          lineStyle: { color: 'rgba(255, 255, 255, 0.15)' }
        },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 11,
          rotate: data.length > 48 ? 45 : 0
        },
        splitLine: {
          show: true,
          lineStyle: { color: 'rgba(255, 255, 255, 0.04)' }
        }
      },
      yAxis: {
        type: 'value',
        name: '₺ / MWh',
        nameTextStyle: {
          color: '#94a3b8',
          fontSize: 12,
          padding: [0, 0, 0, 30]
        },
        axisLine: {
          show: true,
          lineStyle: { color: 'rgba(255, 255, 255, 0.15)' }
        },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 11,
          formatter: '{value} ₺'
        },
        splitLine: {
          lineStyle: { color: 'rgba(255, 255, 255, 0.06)' }
        }
      },
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100
        },
        {
          type: 'slider',
          show: true,
          bottom: '2%',
          height: 20,
          borderColor: 'rgba(255, 255, 255, 0.1)',
          fillerColor: 'rgba(56, 189, 248, 0.2)',
          handleStyle: {
            color: '#38bdf8'
          },
          textStyle: {
            color: '#94a3b8'
          }
        }
      ],
      series: chartSeries
    };
  }, [data, seriesConfigs, intersections, showIntersections, showConfidenceInterval]);

  const onChartClick = (params: any) => {
    if (params.seriesName === 'Kesişim Pingleme' && params.data?.intersectionObj && onIntersectionSelect) {
      onIntersectionSelect(params.data.intersectionObj);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px', position: 'relative' }} id="main-chart-container">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Crosshair size={18} color="#f43f5e" />
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#fff' }}>
            EPİAŞ PTF / SMF vs AI Tahmin Kesişim Grafiği
          </h3>
        </div>
        {showIntersections && intersections.length > 0 && (
          <span className="ping-badge">
            ⚡ {intersections.length} Kesişim Kesişti ve Pinglendi
          </span>
        )}
      </div>

      <div style={{ width: '100%', height: '420px' }}>
        <ReactECharts
          option={option}
          style={{ height: '100%', width: '100%' }}
          onEvents={{ click: onChartClick }}
          notMerge={true}
        />
      </div>
    </div>
  );
};
