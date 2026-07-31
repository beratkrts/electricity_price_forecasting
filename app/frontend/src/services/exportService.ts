import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

export async function exportElementToPNG(elementId: string, filename: string = 'enerji-tahmin-dashboard.png'): Promise<boolean> {
  try {
    const element = document.getElementById(elementId);
    if (!element) {
      console.error(`Export element #${elementId} not found`);
      return false;
    }

    const canvas = await html2canvas(element, {
      scale: 2, // High resolution crisp rendering
      useCORS: true,
      backgroundColor: '#0b0f19', // Match dashboard dark background
      logging: false
    });

    const dataUrl = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = filename;
    link.href = dataUrl;
    link.click();
    return true;
  } catch (error) {
    console.error('PNG export failed:', error);
    return false;
  }
}

export async function exportElementToPDF(
  elementId: string,
  filename: string = 'enerji-tahmin-raporu.pdf',
  reportTitle: string = 'EPİAŞ Enerji Fiyat Tahmin Raporu'
): Promise<boolean> {
  try {
    const element = document.getElementById(elementId);
    if (!element) {
      console.error(`Export element #${elementId} not found`);
      return false;
    }

    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#0b0f19',
      logging: false
    });

    const imgData = canvas.toDataURL('image/jpeg', 0.95);
    const pdf = new jsPDF({
      orientation: 'landscape',
      unit: 'mm',
      format: 'a4'
    });

    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = pdf.internal.pageSize.getHeight();

    // Dark PDF theme header background
    pdf.setFillColor(11, 15, 25);
    pdf.rect(0, 0, pdfWidth, pdfHeight, 'F');

    // Header bar
    pdf.setFillColor(20, 27, 45);
    pdf.rect(0, 0, pdfWidth, 18, 'F');

    // Report Title
    pdf.setTextColor(255, 255, 255);
    pdf.setFontSize(14);
    pdf.text(reportTitle, 10, 12);

    // Timestamp
    pdf.setFontSize(9);
    pdf.setTextColor(156, 163, 175);
    const timeStr = `Rapor Tarihi: ${new Date().toLocaleString('tr-TR')}`;
    pdf.text(timeStr, pdfWidth - 60, 12);

    // Calculate aspect ratio fit for canvas image
    const margin = 10;
    const availableWidth = pdfWidth - margin * 2;
    const availableHeight = pdfHeight - 25 - margin;

    const imgWidth = availableWidth;
    const imgHeight = (canvas.height * imgWidth) / canvas.width;

    const finalHeight = Math.min(imgHeight, availableHeight);

    pdf.addImage(imgData, 'JPEG', margin, 22, imgWidth, finalHeight);

    pdf.save(filename);
    return true;
  } catch (error) {
    console.error('PDF export failed:', error);
    return false;
  }
}
