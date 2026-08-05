import React, { useState } from 'react';
import { Crosshair, Clock, AlertCircle, MoreHorizontal, ChevronUp } from 'lucide-react';
import { IntersectionPoint } from '../../types/energy';
import { formatCurrency, formatToDDMMYYYY } from '../../utils/formatters';

interface IntersectionListProps {
  intersections: IntersectionPoint[];
  selectedIntersection: IntersectionPoint | null;
  onSelectIntersection: (intersection: IntersectionPoint) => void;
}

export const IntersectionList: React.FC<IntersectionListProps> = ({
  intersections,
  selectedIntersection,
  onSelectIntersection
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const displayCount = 5;
  const displayedIntersections = isExpanded ? intersections : intersections.slice(0, displayCount);

  return (
    <div className="glass-panel" style={{ padding: '20px', marginTop: '20px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Crosshair size={18} color="#f43f5e" />
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#fff' }}>
            Kesiştikleri Noktalar
          </h3>
        </div>
        <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
          Toplam <strong>{intersections.length}</strong> Kesişim Noktası Bulundu
        </span>
      </div>

      {intersections.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '24px',
          background: 'rgba(255, 255, 255, 0.02)',
          borderRadius: '12px',
          color: '#64748b',
          fontSize: '0.85rem'
        }}>
          <AlertCircle size={24} style={{ marginBottom: '8px', opacity: 0.6 }} />
          <p>Aktif görünen grafik serileri arasında henüz bir kesişim noktası oluşmadı.</p>
          <p style={{ fontSize: '0.78rem', color: '#475569', marginTop: '4px' }}>
            Sol menüden en az 2 seriyi görünür yaparak kesişimleri görüntüleyebilirsiniz.
          </p>
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
            {displayedIntersections.map((item, idx) => {
              const isSelected = selectedIntersection?.id === item.id;
              return (
                <div
                  key={item.id}
                  onClick={() => onSelectIntersection(item)}
                  style={{
                    background: isSelected ? 'rgba(244, 63, 94, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                    border: `1px solid ${isSelected ? '#f43f5e' : 'rgba(255, 255, 255, 0.08)'}`,
                    borderRadius: '12px',
                    padding: '12px 14px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {/* Time & Ping Badge */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: '#38bdf8', fontWeight: 600 }}>
                      <Clock size={14} />
                      <span>{formatToDDMMYYYY(item.dateLabel)} Saat {item.hourLabel}</span>
                    </div>
                    <span className="ping-badge" style={{ fontSize: '0.7rem', padding: '2px 8px' }}>
                      Kesişim #{idx + 1}
                    </span>
                  </div>

                  {/* Series Names comparison */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', fontSize: '0.82rem' }}>
                    <span style={{ color: item.series1Color, fontWeight: 600 }}>{item.series1Name}</span>
                    <span style={{ color: '#64748b' }}>✕</span>
                    <span style={{ color: item.series2Color, fontWeight: 600 }}>{item.series2Name}</span>
                  </div>

                  {/* Exact Value */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Kesişim Fiyatı:</span>
                    <strong style={{ fontSize: '0.95rem', color: '#fff', fontFamily: 'JetBrains Mono' }}>
                      {formatCurrency(item.exactValue, '₺')}
                    </strong>
                  </div>
                </div>
              );
            })}
          </div>

          {intersections.length > displayCount && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '16px' }}>
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#fff',
                  padding: '6px 16px',
                  borderRadius: '20px',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
                onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'}
                onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'}
              >
                {isExpanded ? (
                  <>
                    <ChevronUp size={16} />
                    Daha Az Göster
                  </>
                ) : (
                  <>
                    <MoreHorizontal size={16} />
                    Tüm {intersections.length} Kesişimi Göster
                  </>
                )}
              </button>
            </div>
          )}
        </>
      )}

    </div>
  );
};
