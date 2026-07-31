import React, { useState, useEffect, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Database, Calendar, Filter, BarChart2, Table as TableIcon, Info, MapPin, TrendingUp, Activity, Layers, X, Plus } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

interface SeriesDef {
  id: string;
  name: string;
  color: string;
  dataKey: string;
  unit: string;
}

const AVAILABLE_SERIES: SeriesDef[] = [
  { id: 'mcp', name: 'Piyasa Takas Fiyatı (PTF)', color: '#38bdf8', dataKey: 'price', unit: '₺/MWh' },
  { id: 'lightgbm', name: 'LightGBM PTF Tahmini (Model)', color: '#c084fc', dataKey: 'price', unit: '₺/MWh' },
  { id: 'smp', name: 'Sistem Marjinal Fiyatı (SMF)', color: '#a855f7', dataKey: 'price', unit: '₺/MWh' },
  { id: 'kgup', name: 'Kesinleşmiş G.Ü.P. (KGÜP)', color: '#fbbf24', dataKey: 'toplam', unit: 'MWh' },
  { id: 'load_forecast', name: 'Yük Tahmini', color: '#10b981', dataKey: 'lep', unit: 'MW' },
  { id: 'actual_generation', name: 'Gerçekleşen Üretim', color: '#f43f5e', dataKey: 'total', unit: 'MWh' },
];

type ChartType = 'line' | 'smooth' | 'area' | 'bar';

interface ActiveLayer {
  id: string; // unique layer instance id
  def: SeriesDef;
  chartType: ChartType;
  data: (number | null)[]; // 24 hours of data
}

export const HistoricalBenchmark: React.FC = () => {
  const [date, setDate] = useState<string>('2026-07-31');
  const [selectedToAdd, setSelectedToAdd] = useState<string>('mcp');
  
  const [activeLayers, setActiveLayers] = useState<ActiveLayer[]>([]);
  const [loading, setLoading] = useState(false);
  const [showTable, setShowTable] = useState(false);
  
  const [pingedHours, setPingedHours] = useState<string[]>([]);

  // Generic fetch for a specific series and date from PostgreSQL database
  const fetchSeriesData = async (seriesId: string, fetchDate: string) => {
    try {
      const res = await fetch(`/api/db-data?date=${fetchDate}&type=${seriesId}`);
      if (!res.ok) return Array(24).fill(null);
      const data = await res.json();
      
      const def = AVAILABLE_SERIES.find(s => s.id === seriesId);
      if (!def || !Array.isArray(data)) {
        return Array(24).fill(null);
      }

      // Parse 24 hours from PostgreSQL query result
      return Array.from({ length: 24 }, (_, i) => {
        const hourStr = i.toString().padStart(2, '0') + ':00';
        const item = data.find((x: any) => x.hour === hourStr);
        if (!item || item[def.dataKey] === undefined || item[def.dataKey] === null) return null;
        
        const val = typeof item[def.dataKey] === 'string' 
            ? parseFloat(item[def.dataKey].replace(',', '.')) 
            : Number(item[def.dataKey]);
            
        return isNaN(val) ? null : val;
      });
    } catch (err) {
      console.error(err);
      return Array(24).fill(null);
    }
  };

  // Load default initial layer (PTF) on mount so chart opens cleanly with PTF
  useEffect(() => {
    let mounted = true;
    const initDefaultLayers = async () => {
      setLoading(true);
      const mcpData = await fetchSeriesData('mcp', date);
      if (!mounted) return;
      setLoading(false);

      const mcpDef = AVAILABLE_SERIES.find(s => s.id === 'mcp')!;

      setActiveLayers([
        { id: `mcp_${Date.now()}`, def: mcpDef, chartType: 'line', data: mcpData }
      ]);
    };

    initDefaultLayers();
    return () => { mounted = false; };
  }, []);

  // When date changes, we should refetch all active layers
  const refetchAllLayers = async () => {
    if (activeLayers.length === 0) return;
    setLoading(true);
    const newLayers = await Promise.all(
      activeLayers.map(async (layer) => {
        const newData = await fetchSeriesData(layer.def.id, date);
        return { ...layer, data: newData };
      })
    );
    setActiveLayers(newLayers);
    setLoading(false);
  };

  const addSeriesLayer = async () => {
    // Determine the actual selected value based on availability
    const availableOptions = AVAILABLE_SERIES.filter(s => !activeLayers.some(l => l.def.id === s.id));
    // If selectedToAdd is not in available, fallback to the first available option
    const actualSelectedId = availableOptions.find(s => s.id === selectedToAdd) ? selectedToAdd : (availableOptions[0]?.id || '');
    
    const def = AVAILABLE_SERIES.find(s => s.id === actualSelectedId);
    if (!def) return;
    
    setLoading(true);
    const newData = await fetchSeriesData(def.id, date);
    setLoading(false);
    
    setActiveLayers(prev => {
      const newLayers = [
        ...prev,
        {
          id: `${def.id}_${Date.now()}`,
          def,
          chartType: 'line' as ChartType,
          data: newData
        }
      ];
      // Update selected to add to next available
      const nextAvailable = AVAILABLE_SERIES.filter(s => !newLayers.some(l => l.def.id === s.id))[0];
      if (nextAvailable) setSelectedToAdd(nextAvailable.id);
      return newLayers;
    });
  };

  const availableSeriesList = useMemo(() => {
    return AVAILABLE_SERIES.filter(s => !activeLayers.some(l => l.def.id === s.id));
  }, [activeLayers]);

  // Keep selectedToAdd always synced with available options
  useEffect(() => {
    if (availableSeriesList.length > 0 && !availableSeriesList.some(s => s.id === selectedToAdd)) {
      setSelectedToAdd(availableSeriesList[0].id);
    }
  }, [availableSeriesList, selectedToAdd]);

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

  const chartOption = useMemo(() => {
    const hours = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0') + ':00');
    
    const isVolumeSeries = (unit: string) => unit === 'MWh' || unit === 'MW';
    const isPriceSeries = (unit: string) => unit === '₺/MWh';

    const hasPrice = activeLayers.some(l => isPriceSeries(l.def.unit));

    const seriesData = activeLayers.map(layer => {
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

      // 0 = Left Axis (Price ₺), 1 = Right Axis (Volume MW/MWh)
      const yAxisIndex = isVolumeSeries(layer.def.unit) ? 1 : 0;

      return {
        name: layer.def.name,
        type,
        smooth,
        areaStyle,
        yAxisIndex,
        data: layer.data,
        itemStyle: { color: layer.def.color },
        lineStyle: { width: 3 }
      };
    });

    const yAxis: any[] = [
      {
        type: 'value',
        name: '₺ / MWh',
        nameTextStyle: { color: '#38bdf8', fontSize: 11 },
        axisLabel: { color: '#38bdf8', formatter: '{value} ₺' },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } }
      },
      {
        type: 'value',
        name: 'MW / MWh',
        nameTextStyle: { color: '#fbbf24', fontSize: 11 },
        axisLabel: { color: '#fbbf24', formatter: '{value}' },
        splitLine: { show: !hasPrice, lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } }
      }
    ];

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.3)',
        textStyle: { color: '#fff', fontSize: 12 }
      },
      legend: {
        show: true,
        textStyle: { color: '#94a3b8' },
        top: '2%'
      },
      grid: { left: '4%', right: '5%', bottom: '8%', top: '16%', containLabel: true },
      xAxis: {
        type: 'category',
        data: hours,
        axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.15)' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 }
      },
      yAxis,
      series: seriesData
    };
  }, [activeLayers]);

  // Utility to get values for a specific hour
  const getValuesForHour = (hour: string) => {
    const hourIdx = parseInt(hour.split(':')[0], 10);
    return activeLayers.map(layer => ({
      name: layer.def.name,
      color: layer.def.color,
      unit: layer.def.unit,
      value: layer.data[hourIdx]
    }));
  };

  return (
    <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* Header & Main Controls */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ padding: '8px', borderRadius: '10px', background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
            <Database size={24} color="#38bdf8" />
          </div>
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff', margin: 0 }}>Dinamik Veri Keşfi</h3>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: 0 }}>İstediğiniz veri setlerini seçin, üst üste bindirin ve karşılaştırın</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: 'rgba(15, 23, 42, 0.6)', padding: '10px 16px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Calendar size={16} color="#94a3b8" />
            <input 
              type="date" 
              value={date}
              onChange={(e) => setDate(e.target.value)}
              style={{
                background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', 
                color: '#fff', borderRadius: '6px', padding: '6px 12px', fontSize: '0.9rem',
                outline: 'none', colorScheme: 'dark'
              }}
            />
          </div>
          <button 
            onClick={refetchAllLayers}
            disabled={loading || activeLayers.length === 0}
            style={{
              background: 'linear-gradient(to right, #3b82f6, #06b6d4)',
              color: '#fff', border: 'none', borderRadius: '6px', padding: '8px 16px',
              fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
              opacity: (loading || activeLayers.length === 0) ? 0.5 : 1, transition: 'all 0.2s'
            }}
          >
            <Filter size={16} />
            {loading ? 'Yükleniyor...' : 'Verileri Güncelle'}
          </button>
        </div>
      </div>

      {/* Dataset Selection & Layer Controls */}
      <div style={{ background: 'rgba(15, 23, 42, 0.4)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', padding: '16px' }}>
        
        {/* Add New Layer */}
        {availableSeriesList.length > 0 && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: activeLayers.length > 0 ? '16px' : '0' }}>
            <span style={{ fontSize: '0.9rem', color: '#fff', fontWeight: 600 }}>Tablo Ekle:</span>
            <select 
              value={selectedToAdd} 
              onChange={(e) => setSelectedToAdd(e.target.value)}
              style={{
                background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.2)', 
                color: '#fff', borderRadius: '6px', padding: '8px 12px', fontSize: '0.85rem', outline: 'none', minWidth: '250px'
              }}
            >
              {availableSeriesList.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <button 
              onClick={addSeriesLayer}
              disabled={loading}
              style={{
                background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.4)', 
                borderRadius: '6px', padding: '8px 16px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', 
                display: 'flex', alignItems: 'center', gap: '6px', transition: 'all 0.2s'
              }}
            >
              <Plus size={16} /> Grafiğe Bindir
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

      {/* Chart */}
      <div style={{ width: '100%', height: '400px', position: 'relative' }}>
        {activeLayers.length === 0 ? (
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px dashed rgba(255,255,255,0.1)' }}>
            <span style={{ color: '#94a3b8' }}>Grafikte veri görmek için yukarıdan tablo seçip "Grafiğe Bindir" butonuna tıklayın.</span>
          </div>
        ) : (
          <>
            <ReactECharts 
              option={chartOption} 
              style={{ height: '100%', width: '100%' }} 
              notMerge={true} 
              onEvents={{ click: handleChartClick }}
            />
            <div style={{ position: 'absolute', top: 8, left: 12, background: 'rgba(15,23,42,0.85)', padding: '6px 12px', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '6px', border: '1px solid rgba(255,255,255,0.1)', pointerEvents: 'none', zIndex: 10 }}>
              <Info size={14} color="#94a3b8" />
              <span style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>Grafik üzerindeki noktalara tıklayarak karşılaştırma pinglemesi yapabilirsiniz</span>
            </div>
          </>
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
      {showTable && activeLayers.length > 0 && (
        <div style={{ overflowX: 'auto', background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', marginTop: '10px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: '#1e293b', color: '#e2e8f0', borderBottom: '2px solid rgba(255, 255, 255, 0.1)' }}>
                <th style={{ padding: '14px 16px', fontWeight: 600, position: 'sticky', left: 0, background: '#1e293b', zIndex: 10 }}>Saat</th>
                {activeLayers.map(layer => (
                  <th key={layer.id} style={{ padding: '14px 16px', fontWeight: 600, color: layer.def.color }}>
                    {layer.def.name} <br/> <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 400 }}>({layer.def.unit})</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 24 }).map((_, idx) => {
                const hourStr = idx.toString().padStart(2, '0') + ':00';
                return (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                      background: idx % 2 === 0 ? 'rgba(255, 255, 255, 0.02)' : 'transparent',
                      transition: 'background 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.08)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = idx % 2 === 0 ? 'rgba(255, 255, 255, 0.02)' : 'transparent'}
                  >
                    <td style={{ padding: '10px 16px', fontWeight: 700, color: '#fff', position: 'sticky', left: 0, background: idx % 2 === 0 ? '#0b1120' : '#070a12' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Calendar size={13} color="#38bdf8" />
                        <span>{hourStr}</span>
                      </div>
                    </td>
                    {activeLayers.map(layer => {
                      const val = layer.data[idx];
                      return (
                        <td key={layer.id} style={{ padding: '10px 16px', fontFamily: 'JetBrains Mono', color: '#e2e8f0' }}>
                          {val !== null ? formatNumber(val, 2) : '-'}
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
