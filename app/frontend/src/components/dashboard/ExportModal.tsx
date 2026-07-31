import React, { useState } from 'react';
import { X, FileImage, FileText, Download, CheckCircle, Loader2 } from 'lucide-react';
import { exportElementToPDF, exportElementToPNG } from '../../services/exportService';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ExportModal: React.FC<ExportModalProps> = ({ isOpen, onClose }) => {
  const [loadingType, setLoadingType] = useState<'png' | 'pdf' | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleExportPNG = async () => {
    setLoadingType('png');
    setSuccessMsg(null);
    const success = await exportElementToPNG('dashboard-export-root', 'epias-enerji-tahmin-dashboard.png');
    setLoadingType(null);
    if (success) {
      setSuccessMsg('PNG dosyası başarıyla indirildi!');
      setTimeout(() => setSuccessMsg(null), 3000);
    }
  };

  const handleExportPDF = async () => {
    setLoadingType('pdf');
    setSuccessMsg(null);
    const success = await exportElementToPDF('dashboard-export-root', 'epias-enerji-tahmin-raporu.pdf');
    setLoadingType(null);
    if (success) {
      setSuccessMsg('PDF raporu başarıyla indirildi!');
      setTimeout(() => setSuccessMsg(null), 3000);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '480px',
        padding: '24px',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        boxShadow: '0 20px 50px rgba(0,0,0,0.8)'
      }}>
        
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Download size={20} color="#38bdf8" />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>
              Dashboard Görünümünü İndir
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '20px', lineHeight: '1.4' }}>
          Grafik ve analiz sonuçlarını yüksek çözünürlüklü <strong>PNG görseli</strong> veya biçimlendirilmiş <strong>PDF raporu</strong> olarak indirebilirsiniz.
        </p>

        {/* Export Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          
          {/* PNG Export */}
          <button
            onClick={handleExportPNG}
            disabled={loadingType !== null}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 18px',
              borderRadius: '12px',
              background: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              color: '#fff',
              fontSize: '0.95rem',
              fontWeight: 600,
              cursor: loadingType ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <FileImage size={24} color="#38bdf8" />
              <div style={{ textAlign: 'left' }}>
                <div>PNG Görsel Olarak İndir</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>Yüksek çözünürlüklü grafik ekran görüntüsü</div>
              </div>
            </div>
            {loadingType === 'png' ? <Loader2 size={20} className="animate-spin" color="#38bdf8" /> : <Download size={18} color="#38bdf8" />}
          </button>

          {/* PDF Export */}
          <button
            onClick={handleExportPDF}
            disabled={loadingType !== null}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 18px',
              borderRadius: '12px',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#fff',
              fontSize: '0.95rem',
              fontWeight: 600,
              cursor: loadingType ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <FileText size={24} color="#10b981" />
              <div style={{ textAlign: 'left' }}>
                <div>PDF Raporu Olarak İndir</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>Metrikler, grafik ve kesişim tablosu içeren PDF</div>
              </div>
            </div>
            {loadingType === 'pdf' ? <Loader2 size={20} className="animate-spin" color="#10b981" /> : <Download size={18} color="#10b981" />}
          </button>

        </div>

        {/* Success Message */}
        {successMsg && (
          <div style={{
            marginTop: '16px',
            padding: '10px 14px',
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid #10b981',
            borderRadius: '8px',
            color: '#10b981',
            fontSize: '0.82rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <CheckCircle size={16} />
            <span>{successMsg}</span>
          </div>
        )}

      </div>
    </div>
  );
};
