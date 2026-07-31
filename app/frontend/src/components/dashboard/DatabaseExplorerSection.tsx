import React, { useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Database, Search, Download, Table as TableIcon, BarChart2, Server, MousePointerClick } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

interface DBTableOption {
  id: string;
  name: string;
  description: string;
  columns: string[];
  color: string;
}

const DB_TABLES: DBTableOption[] = [
  { id: 'raw_mcp_hourly', name: 'raw_mcp_hourly (PTF Fiyatları)', description: 'EPİAŞ Saatlik Piyasa Takas Fiyatı verileri (₺/MWh)', columns: ['price_try', 'price_usd', 'price_eur'], color: '#38bdf8' },
  { id: 'raw_kgup_hourly', name: 'raw_kgup_hourly (KGÜP Üretim Planı)', description: 'Kesinleşmiş Gün Öncesi Santral Üretim Planları (MW)', columns: ['total_mw', 'natural_gas_mw', 'hydro_mw', 'wind_mw', 'lignite_mw'], color: '#fbbf24' },
  { id: 'raw_load_forecast_hourly', name: 'raw_load_forecast_hourly (Yük Tahmini)', description: 'EPİAŞ Saatlik Tüketim Yük Tahmini (MW)', columns: ['load_forecast_mw'], color: '#10b981' },
  { id: 'raw_actual_generation_hourly', name: 'raw_actual_generation_hourly (Gerçekleşen Üretim)', description: 'Kaynak bazlı saatlik gerçekleşen üretim verileri (MW)', columns: ['total_mw', 'natural_gas_mw', 'hydro_mw', 'wind_mw'], color: '#c084fc' },
  { id: 'raw_weather_hourly', name: 'raw_weather_hourly (Hava Durumu)', description: 'Türkiye genel ağırlıklı saatlik sıcaklık (°C)', columns: ['turkey_weighted_temp_c', 'istanbul_temp_c', 'ankara_temp_c'], color: '#f43f5e' },
  { id: 'raw_macro_daily', name: 'raw_macro_daily (Kur & Emtia)', description: 'Günlük USD/TRY, EUR/TRY ve Brent Petrol verileri', columns: ['usd_try', 'eur_try', 'brent_oil_usd'], color: '#e2e8f0' }
];

export const DatabaseExplorerSection: React.FC = () => {
  // Initial state is EMPTY string as requested: "default boş dursun bir şey görünmesin ilk başta"
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterDate, setFilterDate] = useState<string>('2026-07-31');

  const activeTableInfo = DB_TABLES.find((t) => t.id === selectedTable);

  // Generated DB Rows for selectedTable
  const mockTableData = useMemo(() => {
    if (!selectedTable) return [];
    const rows = [];
    const hours = 24;

    for (let h = 0; h < hours; h++) {
      const hourStr = `${h.toString().padStart(2, '0')}:00`;
      const timestamp = `${filterDate} ${hourStr}`;

      if (selectedTable === 'raw_mcp_hourly') {
        const ptfVal = 1850 + (h * 45) + (h % 3 === 0 ? 320 : -50);
        rows.push({
          timestamp,
          price_try: ptfVal,
          price_usd: +(ptfVal / 40.85).toFixed(2),
          price_eur: +(ptfVal / 44.32).toFixed(2),
          created_at: `${filterDate} 04:02:14`
        });
      } else if (selectedTable === 'raw_kgup_hourly') {
        const gas = 8500 + h * 120;
        const hydro = Math.round(6200 + Math.sin(h) * 800);
        const wind = Math.round(4100 + Math.cos(h) * 500);
        const lignite = 5400;
        rows.push({
          timestamp,
          total_mw: gas + hydro + wind + lignite,
          natural_gas_mw: gas,
          hydro_mw: hydro,
          wind_mw: wind,
          lignite_mw: lignite,
          created_at: `${filterDate} 04:02:16`
        });
      } else if (selectedTable === 'raw_load_forecast_hourly') {
        rows.push({
          timestamp,
          load_forecast_mw: Math.round(31000 + Math.sin(h * 0.3) * 6500),
          created_at: `${filterDate} 04:02:18`
        });
      } else if (selectedTable === 'raw_actual_generation_hourly') {
        const gas = 8200 + h * 110;
        const hydro = Math.round(6000 + Math.sin(h) * 750);
        const wind = Math.round(4300 + Math.cos(h) * 480);
        rows.push({
          timestamp,
          total_mw: gas + hydro + wind,
          natural_gas_mw: gas,
          hydro_mw: hydro,
          wind_mw: wind,
          created_at: `${filterDate} 04:02:19`
        });
      } else if (selectedTable === 'raw_weather_hourly') {
        rows.push({
          timestamp,
          turkey_weighted_temp_c: +(24.5 + Math.sin(h * 0.25) * 6.2).toFixed(1),
          istanbul_temp_c: +(26.0 + Math.sin(h * 0.25) * 5.5).toFixed(1),
          ankara_temp_c: +(22.1 + Math.sin(h * 0.25) * 7.8).toFixed(1),
          created_at: `${filterDate} 04:02:20`
        });
      } else {
        rows.push({
          timestamp,
          usd_try: 40.854,
          eur_try: 44.321,
          brent_oil_usd: 78.45,
          created_at: `${filterDate} 04:02:22`
        });
      }
    }

    return rows;
  }, [selectedTable, filterDate]);

  // ECharts Option for Database Explorer Chart View
  const chartOption = useMemo(() => {
    if (!mockTableData || mockTableData.length === 0 || !activeTableInfo) return {};

    const xAxisLabels = mockTableData.map((d) => d.timestamp.slice(11));
    const numCols = activeTableInfo.columns;
    const colors = ['#38bdf8', '#10b981', '#fbbf24', '#c084fc', '#f43f5e'];

    const series = numCols.map((col, idx) => ({
      name: col,
      type: selectedTable.includes('kgup') || selectedTable.includes('generation') ? 'bar' : 'line',
      stack: selectedTable.includes('kgup') ? 'total' : undefined,
      smooth: true,
      data: mockTableData.map((d: any) => d[col]),
      itemStyle: { color: colors[idx % colors.length] }
    }));

    return {
      backgroundColor: 'transparent',
      animationDuration: 600,
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.3)',
        textStyle: { color: '#fff', fontSize: 12 }
      },
      legend: {
        top: '2%',
        right: '2%',
        textStyle: { color: '#94a3b8', fontSize: 11 }
      },
      grid: { top: '15%', left: '3%', right: '3%', bottom: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: xAxisLabels,
        axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.15)' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } }
      },
      series
    };
  }, [mockTableData, activeTableInfo, selectedTable]);

  // Filtered rows for Table View
  const filteredData = useMemo(() => {
    if (!searchQuery) return mockTableData;
    return mockTableData.filter((r) =>
      JSON.stringify(r).toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [mockTableData, searchQuery]);

  const exportCSV = () => {
    if (filteredData.length === 0) return;
    const keys = Object.keys(filteredData[0]);
    let csv = keys.join(',') + '\n';
    filteredData.forEach((row: any) => {
      csv += keys.map((k) => row[k]).join(',') + '\n';
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedTable}_${filterDate}.csv`;
    a.click();
  };

  return (
    <section style={{ marginBottom: '28px' }}>
      
      {/* Section Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(192, 132, 252, 0.2)', color: '#c084fc' }}>
            <Database size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fff', margin: 0 }}>
              BÖLÜM 3: PostgreSQL Veritabanı Veri İnceleyici (Grafik & Tablo Çift Görünüm)
            </h2>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: 0 }}>
              İncelemek istediğiniz veritabanı tablosunu seçin; verileri hem Grafik hem de Tablo formatında sorgulayın
            </p>
          </div>
        </div>

        {/* View Mode Switcher Toggle: Only show when table is selected */}
        {selectedTable && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(15, 23, 42, 0.9)', padding: '4px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <button
              onClick={() => setViewMode('chart')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '8px',
                border: 'none',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: viewMode === 'chart' ? '#38bdf8' : 'transparent',
                color: viewMode === 'chart' ? '#070a12' : '#94a3b8',
                transition: 'all 0.2s ease'
              }}
            >
              <BarChart2 size={15} />
              Grafik Görünümü
            </button>

            <button
              onClick={() => setViewMode('table')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '8px',
                border: 'none',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: viewMode === 'table' ? '#10b981' : 'transparent',
                color: viewMode === 'table' ? '#ffffff' : '#94a3b8',
                transition: 'all 0.2s ease'
              }}
            >
              <TableIcon size={15} />
              Tablo Görünümü
            </button>
          </div>
        )}
      </div>

      <div className="glass-panel" style={{ padding: '20px' }}>
        
        {/* Table Selector Header Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '16px', background: 'rgba(255, 255, 255, 0.02)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
          
          {/* Table selector dropdown */}
          <div style={{ flex: 1, minWidth: '260px' }}>
            <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Veritabanı Tablosunu Seçin:</label>
            <select
              value={selectedTable}
              onChange={(e) => setSelectedTable(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(15, 23, 42, 0.95)',
                border: '1px solid rgba(56, 189, 248, 0.4)',
                color: '#fff',
                padding: '8px 12px',
                borderRadius: '8px',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <option value="">-- Lütfen İncelemek İstediğiniz Tabloyu Seçin --</option>
              {DB_TABLES.map((tbl) => (
                <option key={tbl.id} value={tbl.id}>
                  {tbl.name}
                </option>
              ))}
            </select>
          </div>

          {/* Date Filter & Options if table selected */}
          {selectedTable && (
            <>
              <div>
                <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Tarih Filtresi:</label>
                <input
                  type="date"
                  value={filterDate}
                  onChange={(e) => setFilterDate(e.target.value)}
                  style={{
                    background: 'rgba(15, 23, 42, 0.9)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#fff',
                    padding: '7px 10px',
                    borderRadius: '8px',
                    fontSize: '0.82rem'
                  }}
                />
              </div>

              {viewMode === 'table' && (
                <div style={{ flex: 1, minWidth: '160px' }}>
                  <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Arama:</label>
                  <div style={{ position: 'relative' }}>
                    <Search size={14} color="#94a3b8" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                    <input
                      type="text"
                      placeholder="Filtrele..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{
                        width: '100%',
                        background: 'rgba(15, 23, 42, 0.9)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        color: '#fff',
                        padding: '7px 10px 7px 30px',
                        borderRadius: '8px',
                        fontSize: '0.82rem'
                      }}
                    />
                  </div>
                </div>
              )}

              <div style={{ alignSelf: 'flex-end' }}>
                <button
                  onClick={exportCSV}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.06)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#fff',
                    fontSize: '0.8rem',
                    fontWeight: 500,
                    cursor: 'pointer'
                  }}
                >
                  <Download size={14} />
                  CSV İndir
                </button>
              </div>
            </>
          )}

        </div>

        {/* DEFAULT EMPTY STATE PLACEHOLDER (Starts empty as requested!) */}
        {!selectedTable ? (
          <div style={{
            padding: '36px 20px',
            textAlign: 'center',
            background: 'rgba(255, 255, 255, 0.01)',
            borderRadius: '12px',
            border: '2px dashed rgba(255, 255, 255, 0.08)'
          }}>
            <MousePointerClick size={36} color="#38bdf8" style={{ marginBottom: '12px', opacity: 0.8 }} />
            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginBottom: '6px' }}>
              İncelemek İstediğiniz Veritabanı Tablosunu Seçin
            </h4>
            <p style={{ fontSize: '0.83rem', color: '#94a3b8', maxWidth: '560px', margin: '0 auto 20px auto', lineHeight: '1.4' }}>
              Aşağıdaki veri tablolarından birine tıklayarak PostgreSQL veritabanımızda saklanan zaman serisi verilerini hem <strong>Grafik</strong> hem de <strong>Tablo</strong> modunda inceleyebilirsiniz:
            </p>

            {/* Quick Select Table Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px', textAlign: 'left', maxWidth: '850px', margin: '0 auto' }}>
              {DB_TABLES.map((tbl) => (
                <div
                  key={tbl.id}
                  onClick={() => setSelectedTable(tbl.id)}
                  style={{
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: `1px solid ${tbl.color}40`,
                    borderRadius: '10px',
                    padding: '12px 14px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                  className="glass-panel-interactive"
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: tbl.color }} />
                    <strong style={{ fontSize: '0.85rem', color: '#fff' }}>{tbl.name}</strong>
                  </div>
                  <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: 0, lineHeight: '1.3' }}>
                    {tbl.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          /* TABLE OR CHART DISPLAY WHEN SELECTED */
          <div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Server size={14} color="#38bdf8" />
              <span>{activeTableInfo?.description}</span>
            </div>

            {viewMode === 'chart' ? (
              <div style={{ width: '100%', height: '350px' }}>
                <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} notMerge={true} />
              </div>
            ) : (
              <div style={{ overflowX: 'auto', maxHeight: '350px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255, 255, 255, 0.05)', color: '#38bdf8', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', position: 'sticky', top: 0 }}>
                      {mockTableData.length > 0 &&
                        Object.keys(mockTableData[0]).map((col) => (
                          <th key={col} style={{ padding: '10px 12px', textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.04em' }}>
                            {col}
                          </th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredData.map((row: any, rIdx) => (
                      <tr key={rIdx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                        {Object.keys(row).map((col) => {
                          const val = row[col];
                          const isNum = typeof val === 'number';
                          return (
                            <td key={col} style={{ padding: '8px 12px', fontFamily: isNum ? 'JetBrains Mono' : 'inherit', color: isNum ? '#f8fafc' : '#94a3b8' }}>
                              {isNum ? formatNumber(val, 2) : val}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

      </div>

    </section>
  );
};
