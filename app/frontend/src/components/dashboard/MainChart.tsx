import React, { useMemo, useState, useEffect } from 'react';
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
  currencyMode?: 'TRY' | 'USD';
}

export const MainChart: React.FC<MainChartProps> = ({
  data,
  seriesConfigs,
  intersections,
  showIntersections,
  showConfidenceInterval,
  onIntersectionSelect,
  currencyMode = 'TRY'
}) => {
  const [isLightMode, setIsLightMode] = useState(() => typeof window !== 'undefined' ? localStorage.getItem('etkb_theme') === 'light' : false);
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsLightMode(document.documentElement.getAttribute('data-theme') === 'light');
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  const option = useMemo(() => {
    if (!data || data.length === 0) return {};

    const isLight = isLightMode;
    const gridLineColor = isLight ? 'rgba(0, 0, 0, 0.14)' : 'rgba(255, 255, 255, 0.12)';
    const axisLabelColor = isLight ? '#475569' : '#94a3b8';

    const symbolStr = currencyMode === 'USD' ? '$' : '₺';
    const unitStr = currencyMode === 'USD' ? '$/MWh' : '₺/MWh';

    const xAxisLabels = data.map((d) => `${d.date.slice(5)} ${d.hour}`);

    // Build ECharts series array
    const chartSeries: any[] = [];

    // Add confidence band if enabled
    if (showConfidenceInterval) {
      chartSeries.push({
        name: 'Güven Aralığı Alt',
        type: 'line',
        data: data.map((d) => d.lowerBound),
        lineStyle: { opacity: 0.5, type: 'dashed', width: 1, color: 'rgba(225, 29, 72, 0.4)' },
        stack: 'confidence',
        symbol: 'none',
        silent: true
      });
      chartSeries.push({
        name: 'Güven Aralığı (%80)',
        type: 'line',
        data: data.map((d) => d.upperBound - d.lowerBound),
        lineStyle: { opacity: 0.5, type: 'dashed', width: 1, color: 'rgba(225, 29, 72, 0.4)' },
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

    return {
      backgroundColor: 'transparent',
      animation: true,
      animationDuration: 800,
      tooltip: {
        trigger: 'axis',
        backgroundColor: isLight ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 23, 42, 0.95)',
        borderColor: isLight ? 'rgba(0, 0, 0, 0.1)' : 'rgba(56, 189, 248, 0.3)',
        borderWidth: 1,
        textStyle: {
          color: isLight ? '#0f172a' : '#f8fafc',
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
          const dataIndex = first.dataIndex;
          const pointData = data[dataIndex];
          
          let res = `<div style="font-weight:700;margin-bottom:6px;color:${isLight ? '#0369a1' : '#38bdf8'};">🕒 Saat: ${first.name}</div>`;
          params.forEach((item: any) => {
            if (item.seriesName === 'Kesişim Pingleme' || item.seriesName.includes('Güven Aralığı')) return;
            const val = typeof item.value === 'number' ? item.value.toLocaleString('tr-TR') : item.value;
            res += `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:3px 0;color:${isLight ? '#0f172a' : '#f8fafc'};">
              <span>${item.marker} ${item.seriesName}:</span>
              <strong style="font-family:JetBrains Mono;">${val} ${unitStr}</strong>
            </div>`;
          });

          if (showConfidenceInterval && pointData && pointData.lowerBound && pointData.upperBound) {
            res += `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:3px 0;border-top:1px solid rgba(255,255,255,0.1);padding-top:4px;color:${isLight ? '#0f172a' : '#f8fafc'};">
              <span style="font-size:0.9em;">◬ Güven Aralığı (%80):</span>
              <strong style="font-family:JetBrains Mono;font-size:0.9em;color:#f87171;">[${pointData.lowerBound.toLocaleString('tr-TR')} - ${pointData.upperBound.toLocaleString('tr-TR')}] ${unitStr}</strong>
            </div>`;
          }
          return res;
        }
      },
      legend: {
        show: true,
        top: '2%',
        right: '4%',
        textStyle: {
          color: axisLabelColor,
          fontSize: 11
        }
      },
      grid: {
        top: '12%',
        left: '3%',
        right: '4%',
        bottom: '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: xAxisLabels,
        boundaryGap: false,
        axisLine: {
          lineStyle: { color: isLight ? 'rgba(0, 0, 0, 0.2)' : 'rgba(255, 255, 255, 0.15)' }
        },
        axisLabel: {
          color: axisLabelColor,
          fontSize: 11,
          rotate: data.length > 48 ? 45 : 0
        },
        splitLine: {
          show: true,
          lineStyle: { color: gridLineColor }
        }
      },
      yAxis: {
        type: 'value',
        name: unitStr,
        nameTextStyle: {
          color: axisLabelColor,
          fontSize: 12,
          padding: [0, 0, 0, 30]
        },
        axisLine: {
          show: true,
          lineStyle: { color: isLight ? 'rgba(0, 0, 0, 0.2)' : 'rgba(255, 255, 255, 0.15)' }
        },
        axisLabel: {
          color: axisLabelColor,
          fontSize: 11,
          formatter: `{value} ${symbolStr}`
        },
        splitLine: {
          lineStyle: { color: gridLineColor }
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
  }, [data, seriesConfigs, intersections, showIntersections, showConfidenceInterval, isLightMode]);

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
