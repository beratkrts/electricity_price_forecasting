import React, { useState, useMemo, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { Database, Calendar, Filter, BarChart2, Table as TableIcon, Info, MapPin, TrendingUp, Activity, Layers, X } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

interface SeriesDef {
  id: string;
  name: string;
  color: string;
  dataKey: string;
  unit: string;
}

const AVAILABLE_SERIES: SeriesDef[] = [
  { id: 'mcp', name: 'EPİAŞ Gerçekleşen PTF', color: '#38bdf8', dataKey: 'price', unit: '₺/MWh' },
  { id: 'lightgbm', name: 'Yapay Zeka Fiyat Tahmini', color: '#14b8a6', dataKey: 'price', unit: '₺/MWh' },
  { id: 'smp', name: 'EPİAŞ Dengeleme Fiyatı (SMF)', color: '#f59e0b', dataKey: 'price', unit: '₺/MWh' },
  { id: 'kgup', name: 'Planlanan Üretim (KGÜP)', color: '#06b6d4', dataKey: 'toplam', unit: 'MWh' },
  { id: 'load_forecast', name: 'Şebeke Yük Tahmini', color: '#6366f1', dataKey: 'lep', unit: 'MW' },
  { id: 'actual_generation', name: 'Gerçekleşen Üretim', color: '#f43f5e', dataKey: 'total', unit: 'MWh' },
];

type ChartType = 'line' | 'smooth' | 'area' | 'bar';

interface ActiveLayer {
  id: string; // unique layer instance id
  def: SeriesDef;
  chartType: ChartType;
  data: (number | null)[]; // 24 hours of data
}

interface HistoricalBenchmarkProps {
  currencyMode?: 'TRY' | 'USD';
  usdRate?: number;
}

type CompareMode = 'single' | 'month' | 'year';

const MONTH_NAMES: { [key: string]: string } = {
  '01': 'Ocak', '02': 'Şubat', '03': 'Mart', '04': 'Nisan',
  '05': 'Mayıs', '06': 'Haziran', '07': 'Temmuz', '08': 'Ağustos',
  '09': 'Eylül', '10': 'Ekim', '11': 'Kasım', '12': 'Aralık'
};

const formatMonthLabel = (mStr: string) => {
  if (!mStr || !mStr.includes('-')) return '';
  const [y, m] = mStr.split('-');
  return `${MONTH_NAMES[m] || m} ${y}`;
};

const getMonthRange = (mStr: string) => {
  if (!mStr || !mStr.includes('-')) {
    const d = new Date();
    mStr = `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}`;
  }
  const [y, m] = mStr.split('-').map(Number);
  const now = new Date();
  let lastDay = new Date(y, m, 0).getDate();
  if (y === now.getFullYear() && m === (now.getMonth() + 1)) {
    lastDay = Math.min(lastDay, now.getDate());
  }
  const mFormatted = m.toString().padStart(2, '0');
  return `${y}-${mFormatted}-01_to_${y}-${mFormatted}-${lastDay.toString().padStart(2, '0')}`;
};

const getYearRange = (yStr: string) => {
  if (!yStr) {
    yStr = new Date().getFullYear().toString();
  }
  return `${yStr}-01-01_to_${yStr}-12-31`;
};

export const HistoricalBenchmark: React.FC<HistoricalBenchmarkProps> = ({
  currencyMode = 'TRY',
  usdRate = 33.15
}) => {
  const todayStr = useMemo(() => new Date().toISOString().split('T')[0], []);
  const currentMonthStr = useMemo(() => new Date().toISOString().slice(0, 7), []);
  const currentYearStr = useMemo(() => new Date().getFullYear().toString(), []);

  const [compareMode, setCompareMode] = useState<CompareMode>('single');
  const [date, setDate] = useState<string>(todayStr);
  const [month1, setMonth1] = useState<string>(currentMonthStr);
  const [month2, setMonth2] = useState<string>('');
  const [compareSecondMonth, setCompareSecondMonth] = useState(false);
  const [year1, setYear1] = useState<string>(currentYearStr);
  const [year2, setYear2] = useState<string>('');
  const [compareSecondYear, setCompareSecondYear] = useState(false);

  const [selectedToAdd, setSelectedToAdd] = useState<string>('');
  
  const [activeLayers, setActiveLayers] = useState<ActiveLayer[]>([]);
  const [loading, setLoading] = useState(false);
  const [showTable, setShowTable] = useState(false);
  
  const [pingedHours, setPingedHours] = useState<string[]>([]);

  const [isLightMode, setIsLightMode] = useState(() => typeof window !== 'undefined' ? localStorage.getItem('etkb_theme') === 'light' : false);
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsLightMode(document.documentElement.getAttribute('data-theme') === 'light');
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  const isLight = isLightMode;

  // Generic fetch for a specific series and date from PostgreSQL database
  const fetchSeriesData = async (seriesId: string, fetchDate: string, groupBy?: 'hour' | 'day' | 'month') => {
    try {
      const gParam = groupBy ? `&group_by=${groupBy}` : '';
      const res = await fetch(`/api/db-data?date=${fetchDate}&type=${seriesId}${gParam}`);
      if (!res.ok) return [];
      const data = await res.json();
      
      const def = AVAILABLE_SERIES.find(s => s.id === seriesId);
      if (!def || !Array.isArray(data)) {
        return [];
      }

      if (groupBy === 'month') {
        return Array.from({ length: 12 }, (_, i) => {
          const mStr = (i + 1).toString().padStart(2, '0');
          const item = data.find((x: any) => x.label === mStr);
          if (!item || item[def.dataKey] === undefined || item[def.dataKey] === null) return null;
          const val = typeof item[def.dataKey] === 'string' ? parseFloat(item[def.dataKey].replace(',', '.')) : Number(item[def.dataKey]);
          return isNaN(val) ? null : val;
        });
      } else if (groupBy === 'day') {
        return Array.from({ length: 31 }, (_, i) => {
          const dStr = (i + 1).toString().padStart(2, '0');
          const item = data.find((x: any) => x.label === dStr);
          if (!item || item[def.dataKey] === undefined || item[def.dataKey] === null) return null;
          const val = typeof item[def.dataKey] === 'string' ? parseFloat(item[def.dataKey].replace(',', '.')) : Number(item[def.dataKey]);
          return isNaN(val) ? null : val;
        });
      } else {
        return Array.from({ length: 24 }, (_, i) => {
          const hourStr = i.toString().padStart(2, '0') + ':00';
          const item = data.find((x: any) => x.hour === hourStr);
          if (!item || item[def.dataKey] === undefined || item[def.dataKey] === null) return null;
          const val = typeof item[def.dataKey] === 'string' ? parseFloat(item[def.dataKey].replace(',', '.')) : Number(item[def.dataKey]);
          return isNaN(val) ? null : val;
        });
      }
    } catch (err) {
      console.error(err);
      return [];
    }
  };

  // A period update adds only the requested PTF baseline. Extra series must be
  // selected explicitly below, so SMF and AI forecasts never appear by surprise.
  const refetchAllLayers = async () => {
    if (activeLayers.length === 0) return;
    setLoading(true);
    try {
      const updatedLayers = await Promise.all(activeLayers.map(async (layer) => {
        if (compareMode === 'single') {
          const newData = await fetchSeriesData(layer.def.id, date, 'hour');
          return { ...layer, data: newData, def: { ...layer.def, name: `${layer.def.name.split(' (')[0]} (${date})` } };
        } else if (compareMode === 'month') {
          // If the layer is for month1 or month2
          const isM2 = layer.id.includes('_m2_');
          const m = isM2 ? month2 : month1;
          const range = getMonthRange(m);
          const label = formatMonthLabel(m);
          const newData = await fetchSeriesData(layer.def.id, range, 'day');
          return { ...layer, data: newData, def: { ...layer.def, name: `${layer.def.name.split(' (')[0]} (${label})` } };
        } else if (compareMode === 'year') {
          const isY2 = layer.id.includes('_y2_');
          const y = isY2 ? year2 : year1;
          const range = getYearRange(y);
          const newData = await fetchSeriesData(layer.def.id, range, 'month');
          return { ...layer, data: newData, def: { ...layer.def, name: `${layer.def.name.split(' (')[0]} (${y} Yılı)` } };
        }
        return layer;
      }));
      setActiveLayers(updatedLayers);
    } finally {
      setLoading(false);
    }
  };

const COLOR_PALETTE = [
  '#38bdf8', // Sky Blue
  '#14b8a6', // Teal
  '#f59e0b', // Amber
  '#8b5cf6', // Violet
  '#f43f5e', // Rose Red
  '#a855f7', // Violet
  '#06b6d4', // Cyan
  '#f97316', // Orange
  '#e11d48', // Crimson
  '#84cc16', // Lime
  '#c084fc'  // Purple
];

  const addSeriesLayer = async () => {
    const def = AVAILABLE_SERIES.find(s => s.id === selectedToAdd);
    if (!def) return;

    setLoading(true);

    if (compareMode === 'single') {
      const newData = await fetchSeriesData(def.id, date, 'hour');
      const color = COLOR_PALETTE[activeLayers.length % COLOR_PALETTE.length];
      setActiveLayers(prev => [
        ...prev,
        {
          id: `${def.id}_${Date.now()}`,
          def: { ...def, name: `${def.name} (${date})`, color },
          chartType: 'line' as ChartType,
          data: newData
        }
      ]);
    } else if (compareMode === 'month') {
      const range1 = getMonthRange(month1);
      const data1 = await fetchSeriesData(def.id, range1, 'day');
      
      const label1 = formatMonthLabel(month1);
      const label2 = formatMonthLabel(month2);
      const color1 = COLOR_PALETTE[activeLayers.length % COLOR_PALETTE.length];
      const color2 = COLOR_PALETTE[(activeLayers.length + 1) % COLOR_PALETTE.length];

      const primaryLayer: ActiveLayer = {
        id: `${def.id}_m1_${Date.now()}`,
        def: { ...def, name: `${def.name} (${label1})`, color: color1 },
        chartType: 'line', data: data1
      };
      if (!compareSecondMonth || !month2 || month1 === month2) {
        setActiveLayers(prev => [...prev, primaryLayer]);
      } else {
        const data2 = await fetchSeriesData(def.id, getMonthRange(month2), 'day');
        setActiveLayers(prev => [...prev, primaryLayer, {
          id: `${def.id}_m2_${Date.now()}`,
          def: { ...def, name: `${def.name} (${label2})`, color: color2 },
          chartType: 'line', data: data2
        }]);
      }
    } else if (compareMode === 'year') {
      const range1 = getYearRange(year1);
      const data1 = await fetchSeriesData(def.id, range1, 'month');

      const color1 = COLOR_PALETTE[activeLayers.length % COLOR_PALETTE.length];
      const color2 = COLOR_PALETTE[(activeLayers.length + 1) % COLOR_PALETTE.length];

      const primaryLayer: ActiveLayer = {
        id: `${def.id}_y1_${Date.now()}`,
        def: { ...def, name: `${def.name} (${year1} Ort.)`, color: color1 },
        chartType: 'line', data: data1
      };
      if (!compareSecondYear || !year2 || year1 === year2) {
        setActiveLayers(prev => [...prev, primaryLayer]);
      } else {
        const data2 = await fetchSeriesData(def.id, getYearRange(year2), 'month');
        setActiveLayers(prev => [...prev, primaryLayer, {
          id: `${def.id}_y2_${Date.now()}`,
          def: { ...def, name: `${def.name} (${year2} Ort.)`, color: color2 },
          chartType: 'line', data: data2
        }]);
      }
    }

    setLoading(false);
  };

  const availableSeriesList = AVAILABLE_SERIES;

  const removeLayer = (layerId: string) => {
    setActiveLayers(prev => prev.filter(l => l.id !== layerId));
  };

  const changeLayerChartType = (layerId: string, type: ChartType) => {
    setActiveLayers(prev => prev.map(l => l.id === layerId ? { ...l, chartType: type } : l));
  };

  const handleChartClick = (e: any) => {
    if (e.componentType === 'series') {
      const idx = e.dataIndex;
      const hourStr = idx.toString().padStart(2, '0') + ':00';
      if (!pingedHours.includes(hourStr)) {
        setPingedHours(prev => [...prev, hourStr]);
      }
    }
  };

  const removePing = (hour: string) => {
    setPingedHours(prev => prev.filter(h => h !== hour));
  };

  const displayLayers = useMemo(() => {
    const fallbackRate = usdRate > 0 ? usdRate : 33.15;
    return activeLayers.map(layer => {
      const isPrice = layer.def.unit.includes('₺') || layer.def.id === 'mcp' || layer.def.id === 'lightgbm' || layer.def.id === 'smp';
      const unit = isPrice ? (currencyMode === 'USD' ? '$/MWh' : '₺/MWh') : layer.def.unit;
      const data = layer.data.map(val => {
        if (val === null || val === undefined) return null;
        return isPrice && currencyMode === 'USD' ? Number((val / fallbackRate).toFixed(2)) : val;
      });
      return {
        ...layer,
        def: { ...layer.def, unit },
        data
      };
    });
  }, [activeLayers, currencyMode, usdRate]);

  const xAxisLabels = useMemo(() => {
    if (compareMode === 'year') {
      return ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
    } else if (compareMode === 'month') {
      return Array.from({ length: 31 }, (_, i) => `${i + 1}. Gün`);
    } else {
      return Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0') + ':00');
    }
  }, [compareMode]);

  const chartOption = useMemo(() => {
    if (activeLayers.length === 0) return {};

    const gridColor = isLight ? 'rgba(0, 0, 0, 0.14)' : 'rgba(255, 255, 255, 0.12)';
    const textColor = isLight ? '#475569' : '#94a3b8';
    const isVolumeSeries = (unit: string) => unit === 'MWh' || unit === 'MW';
    const isPriceSeries = (unit: string) => unit.includes('/MWh') && !isVolumeSeries(unit);

    const hasPrice = displayLayers.some(l => isPriceSeries(l.def.unit));

    const seriesData = displayLayers.map(layer => {
      let type = 'line';
      let areaStyle = undefined;
      let smooth = false;

      if (layer.chartType === 'smooth') {
        type = 'line';
        smooth = true;
      } else if (layer.chartType === 'area') {
        type = 'line';
        areaStyle = { opacity: 0.3 };
      } else if (layer.chartType === 'bar') {
        type = 'bar';
      }

      // 0 = Left Axis (Price ₺/$), 1 = Right Axis (Volume MW/MWh)
      const yAxisIndex = isVolumeSeries(layer.def.unit) ? 1 : 0;

      return {
        name: layer.def.name,
        type,
        smooth,
        areaStyle,
        yAxisIndex,
        data: layer.data,
        itemStyle: { color: layer.def.color },
        lineStyle: { width: 3, color: layer.def.color },
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        emphasis: { focus: 'series', lineStyle: { width: 4 } }
      };
    });

    const priceUnit = currencyMode === 'USD' ? '$/MWh' : '₺/MWh';
    const priceSymbol = currencyMode === 'USD' ? '$' : '₺';

    const yAxis: any[] = [
      {
        type: 'value',
        name: priceUnit,
        nameTextStyle: { color: isLight ? '#0369a1' : '#38bdf8', fontSize: 11 },
        axisLabel: { color: isLight ? '#0369a1' : '#38bdf8', formatter: `{value} ${priceSymbol}` },
        splitLine: { lineStyle: { color: gridColor } }
      },
      {
        type: 'value',
        name: 'MW / MWh',
        nameTextStyle: { color: isLight ? '#b45309' : '#f59e0b', fontSize: 11 },
        axisLabel: { color: isLight ? '#b45309' : '#f59e0b', formatter: '{value}' },
        splitLine: { show: !hasPrice, lineStyle: { color: gridColor } }
      }
    ];

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: isLight ? 'rgba(255, 255, 255, 0.98)' : 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.3)',
        textStyle: { color: isLight ? '#0f172a' : '#fff', fontSize: 12 }
      },
      legend: {
        show: true,
        textStyle: { color: textColor },
        top: '2%',
        icon: 'roundRect',
        itemWidth: 12,
        itemHeight: 3
      },
      grid: { left: '4%', right: '5%', bottom: '13%', top: '16%', containLabel: true },
      xAxis: {
        type: 'category',
        data: xAxisLabels,
        axisLine: { lineStyle: { color: gridColor } },
        axisLabel: { color: textColor, fontSize: 11 },
        splitLine: { show: true, lineStyle: { color: gridColor } }
      },
      yAxis,
      dataZoom: [{ type: 'inside' }, {
        type: 'slider', bottom: '2%', height: 18,
        borderColor: isLight ? '#cbd5e1' : 'rgba(148, 163, 184, 0.24)',
        fillerColor: isLight ? 'rgba(14, 165, 233, 0.16)' : 'rgba(56, 189, 248, 0.18)',
        handleStyle: { color: '#38bdf8' },
        textStyle: { color: textColor }
      }],
      series: seriesData
    };
  }, [displayLayers, currencyMode, xAxisLabels, isLightMode]);

  // Utility to get values for a specific hour/label
  const getValuesForHour = (hour: string) => {
    const idx = xAxisLabels.indexOf(hour);
    const hourIdx = idx >= 0 ? idx : parseInt(hour.split(':')[0], 10);
    return displayLayers.map(layer => ({
      name: layer.def.name,
      color: layer.def.color,
      unit: layer.def.unit,
      value: layer.data[hourIdx] !== undefined ? layer.data[hourIdx] : null
    }));
  };

  return (
    <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* Header & Main Controls */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ padding: '8px', borderRadius: '10px', background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
            <Database size={24} color="#38bdf8" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fff', margin: 0 }}>Detaylı Piyasa Analizi</h2>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: 0 }}>Piyasa verilerini ve tahmin modellerini grafik üzerinde karşılaştırmalı olarak inceleyin</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', width: '100%' }}>
          
          {/* Comparison Mode Switcher */}
          <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.6)', padding: '4px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
            {[
              { id: 'single', label: 'Tek Gün' },
              { id: 'month', label: 'Ay Bazlı Kıyaslama' },
              { id: 'year', label: 'Yıl Bazlı Kıyaslama' }
            ].map(m => (
              <button
                key={m.id}
                onClick={() => setCompareMode(m.id as CompareMode)}
                style={{
                  background: compareMode === m.id ? '#38bdf8' : 'transparent',
                  color: compareMode === m.id ? '#0f172a' : '#94a3b8',
                  border: 'none',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Conditional Date / Period Pickers */}
          {compareMode === 'single' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.6)', padding: '6px 12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
              <Calendar size={16} color="#94a3b8" />
              <input 
                type="date" 
                min="2023-01-01"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                style={{
                  background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', 
                  color: '#fff', borderRadius: '6px', padding: '6px 12px', fontSize: '0.85rem',
                  outline: 'none', colorScheme: 'dark'
                }}
              />
            </div>
          )}

          {compareMode === 'month' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(15, 23, 42, 0.6)', padding: '6px 12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
              <Calendar size={16} color="#38bdf8" />
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>1. Ay:</span>
                <input 
                  type="month" 
                  min="2023-01"
                  value={month1}
                  onChange={(e) => setMonth1(e.target.value)}
                  style={{
                    background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', 
                    color: '#fff', borderRadius: '6px', padding: '4px 8px', fontSize: '0.82rem',
                    outline: 'none', colorScheme: 'dark'
                  }}
                />
              </div>
              <span style={{ color: '#64748b', fontSize: '0.8rem' }}>vs</span>
              <label style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#94a3b8', fontSize: '0.75rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={compareSecondMonth} onChange={(e) => { setCompareSecondMonth(e.target.checked); if (!e.target.checked) setMonth2(''); }} />
                Karşılaştır
              </label>
              {compareSecondMonth && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>2. Ay:</span>
                <input 
                  type="month" 
                  min="2023-01"
                  value={month2}
                  onChange={(e) => setMonth2(e.target.value)}
                  style={{
                    background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', 
                    color: '#fff', borderRadius: '6px', padding: '4px 8px', fontSize: '0.82rem',
                    outline: 'none', colorScheme: 'dark'
                  }}
                />
              </div>
              )}
            </div>
          )}

          {compareMode === 'year' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(15, 23, 42, 0.6)', padding: '6px 12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
              <Calendar size={16} color="#fbbf24" />
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>1. Yıl:</span>
                <select
                  value={year1}
                  onChange={(e) => setYear1(e.target.value)}
                  style={{
                    background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', 
                    color: '#fff', borderRadius: '6px', padding: '4px 8px', fontSize: '0.82rem', outline: 'none'
                  }}
                >
                  <option value="2023">2023</option>
                  <option value="2024">2024</option>
                  <option value="2025">2025</option>
                  <option value="2026">2026</option>
                </select>
              </div>
              <span style={{ color: '#64748b', fontSize: '0.8rem' }}>vs</span>
              <label style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#94a3b8', fontSize: '0.75rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={compareSecondYear} onChange={(e) => { setCompareSecondYear(e.target.checked); if (!e.target.checked) setYear2(''); }} />
                Karşılaştır
              </label>
              {compareSecondYear && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>2. Yıl:</span>
                <select
                  value={year2}
                  onChange={(e) => setYear2(e.target.value)}
                  style={{
                    background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', 
                    color: '#fff', borderRadius: '6px', padding: '4px 8px', fontSize: '0.82rem', outline: 'none'
                  }}
                >
                  <option value="2023">2023</option>
                  <option value="2024">2024</option>
                  <option value="2025">2025</option>
                  <option value="2026">2026</option>
                </select>
              </div>
              )}
            </div>
          )}


        </div>
      </div>

      {/* Dataset Selection & Layer Controls */}
      <div style={{ background: 'rgba(15, 23, 42, 0.4)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', padding: '16px' }}>
        
        {/* Add New Layer */}
        {availableSeriesList.length > 0 && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: activeLayers.length > 0 ? '16px' : '0' }}>
            <span style={{ fontSize: '0.9rem', color: '#fff', fontWeight: 600 }}>Veri Serisi Ekle:</span>
            <select 
              value={selectedToAdd} 
              onChange={(e) => setSelectedToAdd(e.target.value)}
              style={{
                background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.2)', 
                color: '#fff', borderRadius: '6px', padding: '8px 12px', fontSize: '0.85rem', outline: 'none', minWidth: '250px'
              }}
            >
              <option value="" disabled>Veri serisi seçin</option>
              {availableSeriesList.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <button 
              onClick={() => {
                if (selectedToAdd) {
                  addSeriesLayer().then(() => setSelectedToAdd(''));
                } else {
                  refetchAllLayers();
                }
              }}
              disabled={loading || (!selectedToAdd && activeLayers.length === 0)}
              style={{
                background: 'linear-gradient(to right, #3b82f6, #06b6d4)',
                color: '#fff', border: 'none', borderRadius: '6px', padding: '8px 16px',
                fontSize: '0.85rem', fontWeight: 600, cursor: (loading || (!selectedToAdd && activeLayers.length === 0)) ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
                opacity: (loading || (!selectedToAdd && activeLayers.length === 0)) ? 0.5 : 1, transition: 'all 0.2s'
              }}
            >
              <Filter size={16} />
              {loading ? 'Yükleniyor...' : 'Grafiği Göster'}
            </button>
          </div>
        )}

        {/* Active Layers Config */}
        {activeLayers.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ height: '1px', background: 'rgba(255,255,255,0.1)', marginBottom: '4px' }}></div>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Aktif Veri Katmanları</span>
            
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
              {activeLayers.map((layer) => (
                <div key={layer.id} style={{
                  display: 'flex', alignItems: 'center', gap: '12px', background: 'rgba(0,0,0,0.3)', 
                  border: `1px solid ${layer.def.color}40`, padding: '6px 12px', borderRadius: '8px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: layer.def.color }}></div>
                    <span style={{ color: '#fff', fontSize: '0.85rem', fontWeight: 500 }}>{layer.def.name}</span>
                  </div>
                  
                  <div style={{ width: '1px', height: '16px', background: 'rgba(255,255,255,0.2)' }}></div>
                  
                  {/* Chart Type Icons */}
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button 
                      title="Çizgi"
                      onClick={() => changeLayerChartType(layer.id, 'line')}
                      style={{ background: layer.chartType === 'line' ? 'rgba(255,255,255,0.15)' : 'transparent', border: 'none', color: layer.chartType === 'line' ? '#fff' : '#64748b', padding: '4px', borderRadius: '4px', cursor: 'pointer' }}
                    ><TrendingUp size={16} /></button>
                    <button 
                      title="Yumuşak (Eğri)"
                      onClick={() => changeLayerChartType(layer.id, 'smooth')}
                      style={{ background: layer.chartType === 'smooth' ? 'rgba(255,255,255,0.15)' : 'transparent', border: 'none', color: layer.chartType === 'smooth' ? '#fff' : '#64748b', padding: '4px', borderRadius: '4px', cursor: 'pointer' }}
                    ><Activity size={16} /></button>
                    <button 
                      title="Alan Grafiği"
                      onClick={() => changeLayerChartType(layer.id, 'area')}
                      style={{ background: layer.chartType === 'area' ? 'rgba(255,255,255,0.15)' : 'transparent', border: 'none', color: layer.chartType === 'area' ? '#fff' : '#64748b', padding: '4px', borderRadius: '4px', cursor: 'pointer' }}
                    ><Layers size={16} /></button>
                    <button 
                      title="Sütun"
                      onClick={() => changeLayerChartType(layer.id, 'bar')}
                      style={{ background: layer.chartType === 'bar' ? 'rgba(255,255,255,0.15)' : 'transparent', border: 'none', color: layer.chartType === 'bar' ? '#fff' : '#64748b', padding: '4px', borderRadius: '4px', cursor: 'pointer' }}
                    ><BarChart2 size={16} /></button>
                  </div>
                  
                  <div style={{ width: '1px', height: '16px', background: 'rgba(255,255,255,0.2)' }}></div>
                  
                  <button 
                    onClick={() => removeLayer(layer.id)}
                    style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center' }}
                  >
                    <X size={16} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Info Banner Above Chart */}
      {activeLayers.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px', padding: '6px 12px', background: 'rgba(56, 189, 248, 0.08)', borderRadius: '6px', border: '1px solid rgba(56, 189, 248, 0.2)', width: 'fit-content' }}>
          <Info size={14} color="#38bdf8" />
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 500 }}>Grafik üzerindeki noktalara tıklayarak karşılaştırma pinglemesi yapabilirsiniz</span>
        </div>
      )}

      {/* Chart */}
      <div style={{ width: '100%', height: '400px', position: 'relative' }}>
        {activeLayers.length === 0 ? (
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px dashed rgba(255,255,255,0.1)' }}>
            <span style={{ color: '#94a3b8' }}>Grafikte veri görmek için yukarıdan veri serisi seçip "Grafiği Göster" butonuna tıklayın.</span>
          </div>
        ) : (
          <ReactECharts 
            option={chartOption} 
            style={{ height: '100%', width: '100%' }} 
            notMerge={true} 
            onEvents={{ click: handleChartClick }}
          />
        )}
      </div>

      {/* Pinged Cards */}
      {pingedHours.length > 0 && (
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginTop: '10px' }}>
          {pingedHours.map((hour, idx) => {
            const vals = getValuesForHour(hour);
            return (
              <div key={idx} style={{ 
                background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(56, 189, 248, 0.4)', 
                borderRadius: '12px', padding: '16px', minWidth: '220px', position: 'relative',
                boxShadow: '0 4px 20px rgba(0,0,0,0.4)', flex: '1 1 220px', maxWidth: '300px'
              }}>
                <button 
                  onClick={() => removePing(hour)}
                  style={{ position: 'absolute', top: '12px', right: '12px', background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
                ><X size={16} /></button>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '10px' }}>
                  <MapPin size={18} color="#38bdf8" />
                  <span style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>Saat {hour}</span>
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {vals.map((v, vIdx) => (
                    <div key={vIdx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span style={{ color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: v.color }}></span>
                        {v.name}
                      </span>
                      <strong style={{ color: '#fff', fontFamily: 'JetBrains Mono' }}>
                        {v.value !== null ? `${formatNumber(v.value, 2)} ${v.unit}` : '-'}
                      </strong>
                    </div>
                  ))}
                  {vals.length === 0 && <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Veri yok</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Table Toggle */}
      {activeLayers.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px' }}>
          <button
            onClick={() => setShowTable(!showTable)}
            style={{
              background: showTable ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              border: `1px solid ${showTable ? 'rgba(56, 189, 248, 0.4)' : 'rgba(255, 255, 255, 0.1)'}`,
              color: showTable ? '#38bdf8' : '#94a3b8',
              padding: '10px 24px', borderRadius: '24px', fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.2s'
            }}
          >
            <TableIcon size={18} />
            {showTable ? 'Tablo Görünümünü Gizle' : 'Tablo Görünümünü Aç'}
          </button>
        </div>
      )}

      {/* Unified Table Container */}
      {displayLayers.length > 0 && (
        <div className={`${!showTable ? 'hide-on-screen' : ''} export-expandable-table`} style={{ overflowX: 'auto', background: isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255,255,255,0.05)', marginTop: '10px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: isLight ? '#f1f5f9' : '#1e293b', color: isLight ? '#0f172a' : '#e2e8f0', borderBottom: isLight ? '2px solid #cbd5e1' : '2px solid rgba(255, 255, 255, 0.1)' }}>
                <th style={{ padding: '14px 16px', fontWeight: 600, position: 'sticky', left: 0, background: isLight ? '#f1f5f9' : '#1e293b', zIndex: 10 }}>
                  {compareMode === 'year' ? 'Aylar' : (compareMode === 'month' ? 'Günler' : 'Saat')}
                </th>
                {displayLayers.map(layer => (
                  <th key={layer.id} style={{ padding: '14px 16px', fontWeight: 600, color: layer.def.color }}>
                    {layer.def.name} <br/> <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 400 }}>({layer.def.unit})</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {xAxisLabels.map((label, idx) => {
                return (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255, 255, 255, 0.04)',
                      background: isLight ? (idx % 2 === 0 ? '#fafaf9' : '#ffffff') : (idx % 2 === 0 ? 'rgba(255, 255, 255, 0.02)' : 'transparent'),
                      transition: 'background 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = isLight ? '#e2e8f0' : 'rgba(56, 189, 248, 0.08)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = isLight ? (idx % 2 === 0 ? '#fafaf9' : '#ffffff') : (idx % 2 === 0 ? 'rgba(255, 255, 255, 0.02)' : 'transparent')}
                  >
                    <td style={{ padding: '10px 16px', fontWeight: 700, color: isLight ? '#0f172a' : '#fff', position: 'sticky', left: 0, background: isLight ? (idx % 2 === 0 ? '#fafaf9' : '#ffffff') : (idx % 2 === 0 ? '#0b1120' : '#070a12'), zIndex: 5, borderRight: isLight ? '1px solid #e2e8f0' : 'none' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Calendar size={13} color={isLight ? '#0ea5e9' : '#38bdf8'} />
                        <span>{label}</span>
                      </div>
                    </td>
                    {displayLayers.map(layer => {
                      const val = layer.data[idx];
                      return (
                        <td key={layer.id} style={{ padding: '10px 16px', fontFamily: 'JetBrains Mono', color: val !== null ? (isLight ? '#0f172a' : '#fff') : (isLight ? '#94a3b8' : '#64748b') }}>
                          {val !== null && val !== undefined ? formatNumber(val, 2) : '-'}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
};
