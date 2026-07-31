import React, { useState, useMemo } from 'react';
import { Database, Search, Download, Table, Server } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

interface DBTableOption {
  id: string;
  name: string;
  description: string;
  recordCount: number;
}

const DB_TABLES: DBTableOption[] = [
  { id: 'raw_mcp_hourly', name: 'raw_mcp_hourly (PTF Fiyatları)', description: 'EPİAŞ Saatlik Piyasa Takas Fiyatı verileri (₺/MWh)', recordCount: 22632 },
  { id: 'raw_kgup_hourly', name: 'raw_kgup_hourly (KGÜP Planı)', description: 'Kesinleşmiş Gün Öncesi Santral Üretim Planları (MW)', recordCount: 22632 },
  { id: 'raw_load_forecast_hourly', name: 'raw_load_forecast_hourly (Yük Tahmini)', description: 'EPİAŞ Saatlik Tüketim Yük Tahmini (MW)', recordCount: 22632 },
  { id: 'raw_actual_generation_hourly', name: 'raw_actual_generation_hourly (Gerçekleşen Üretim)', description: 'Kaynak bazlı saatlik gerçekleşen üretim verileri (MW)', recordCount: 22632 },
  { id: 'raw_weather_hourly', name: 'raw_weather_hourly (Hava Durumu)', description: 'Türkiye genel ağırlıklı saatlik sıcaklık (°C)', recordCount: 22632 },
  { id: 'raw_macro_daily', name: 'raw_macro_daily (Kur & Emtia)', description: 'Günlük USD/TRY, EUR/TRY ve Brent Petrol verileri', recordCount: 945 }
];

export const DatabaseExplorer: React.FC = () => {
  const [selectedTable, setSelectedTable] = useState<string>('raw_mcp_hourly');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterDate, setFilterDate] = useState<string>('2026-07-31');

  // Simulated Database Rows based on selectedTable
  const mockTableData = useMemo(() => {
    const rows = [];
    const hours = 24;

    for (let h = 0; h < hours; h++) {
      const hourStr = `${h.toString().padStart(2, '0')}:00`;
      const timestamp = `${filterDate} ${hourStr}`;

      if (selectedTable === 'raw_mcp_hourly') {
        rows.push({
          timestamp,
          price_try: 1850 + (h * 45) + (h % 3 === 0 ? 320 : -50),
          price_usd: +( (1850 + h * 45) / 40.85 ).toFixed(2),
          price_eur: +( (1850 + h * 45) / 44.32 ).toFixed(2),
          period_key: filterDate.slice(0, 7),
          created_at: `${filterDate} 04:02:14`
        });
      } else if (selectedTable === 'raw_kgup_hourly') {
        rows.push({
          timestamp,
          natural_gas_mw: 8500 + h * 120,
          hydro_mw: 6200 + Math.sin(h) * 800,
          wind_mw: 4100 + Math.cos(h) * 500,
          lignite_mw: 5400,
          total_mw: 24200 + h * 300,
          created_at: `${filterDate} 04:02:16`
        });
      } else if (selectedTable === 'raw_load_forecast_hourly') {
        rows.push({
          timestamp,
          load_forecast_mw: Math.round(31000 + Math.sin(h * 0.3) * 6500),
          created_at: `${filterDate} 04:02:18`
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

  // Filtered rows
  const filteredData = useMemo(() => {
    if (!searchQuery) return mockTableData;
    return mockTableData.filter((r) =>
      JSON.stringify(r).toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [mockTableData, searchQuery]);

  const activeTableInfo = DB_TABLES.find((t) => t.id === selectedTable);

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
    <div className="glass-panel" style={{ padding: '20px', marginTop: '20px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Database size={20} color="#38bdf8" />
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', margin: 0 }}>
              PostgreSQL Veritabanı Tablo İnceleyici (DB Explorer)
            </h3>
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', margin: 0 }}>
              `enerji_fiyat_tahmini` veritabanındaki Bronze/Silver zaman serisi tablolarını canlı sorgulama
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.78rem', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.12)', padding: '4px 10px', borderRadius: '6px', fontWeight: 600 }}>
            <Server size={12} style={{ marginRight: '4px' }} />
            PostgreSQL Bağıntısı Aktif
          </span>
          <button
            onClick={exportCSV}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
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
      </div>

      {/* Control Bar: Table Select, Date Picker, Search */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '16px', background: 'rgba(255, 255, 255, 0.02)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
        
        {/* Table selector */}
        <div style={{ flex: 1, minWidth: '240px' }}>
          <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>Veritabanı Tablosu:</label>
          <select
            value={selectedTable}
            onChange={(e) => setSelectedTable(e.target.value)}
            style={{
              width: '100%',
              background: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              color: '#fff',
              padding: '8px 12px',
              borderRadius: '8px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {DB_TABLES.map((tbl) => (
              <option key={tbl.id} value={tbl.id}>
                {tbl.name}
              </option>
            ))}
          </select>
        </div>

        {/* Date Filter */}
        <div>
          <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>Tarih Filtresi:</label>
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

        {/* Search Input */}
        <div style={{ flex: 1, minWidth: '200px' }}>
          <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>Tabloda Arama Yap:</label>
          <div style={{ position: 'relative' }}>
            <Search size={15} color="#94a3b8" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Fiyat, MW, Saat ara..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(15, 23, 42, 0.9)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                color: '#fff',
                padding: '7px 10px 7px 32px',
                borderRadius: '8px',
                fontSize: '0.82rem'
              }}
            />
          </div>
        </div>

      </div>

      {/* Description tag */}
      {activeTableInfo && (
        <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Table size={14} color="#38bdf8" />
          <span>{activeTableInfo.description} &bull; Toplam <strong>{activeTableInfo.recordCount.toLocaleString('tr-TR')}</strong> kayıt mevcut</span>
        </div>
      )}

      {/* Data Table */}
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
              <tr
                key={rIdx}
                style={{
                  borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                  transition: 'background 0.15s ease'
                }}
              >
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

    </div>
  );
};
