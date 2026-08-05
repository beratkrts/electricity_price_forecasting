import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

export async function exportElementToPNG(elementId: string, filename: string = 'enerji-tahmin-dashboard.png'): Promise<boolean> {
  try {
    const element = document.getElementById(elementId);
    if (!element) {
      console.error(`Export element #${elementId} not found`);
      return false;
    }

    document.body.classList.add('is-exporting');
    
    // Give browser a tick to apply display block
    await new Promise(resolve => setTimeout(resolve, 50));

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
  } finally {
    document.body.classList.remove('is-exporting');
  }
}

export async function exportElementToPDF(
  elementId: string,
  filename: string = 'enerji-tahmin-raporu.pdf',
  reportTitle: string = 'Enerji Fiyat Tahmin Raporu'
): Promise<boolean> {
  try {
    const element = document.getElementById(elementId);
    if (!element) {
      console.error(`Export element #${elementId} not found`);
      return false;
    }

    document.body.classList.add('is-exporting');
    
    // Give browser a tick to apply display block
    await new Promise(resolve => setTimeout(resolve, 50));

    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#0b0f19',
      logging: false
    });

    const imgData = canvas.toDataURL('image/jpeg', 0.95);
    
    // Create PDF with exact canvas dimensions (plus header) for perfect aspect ratio
    const headerHeight = Math.max(120, canvas.width * 0.06); // scale header height based on width
    const pdf = new jsPDF({
      orientation: canvas.width > canvas.height ? 'landscape' : 'portrait',
      unit: 'px',
      format: [canvas.width, canvas.height + headerHeight]
    });

    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = pdf.internal.pageSize.getHeight();

    // Dark PDF theme background
    pdf.setFillColor(11, 15, 25);
    pdf.rect(0, 0, pdfWidth, pdfHeight, 'F');

    // Header bar
    pdf.setFillColor(20, 27, 45);
    pdf.rect(0, 0, pdfWidth, headerHeight, 'F');

    // Report Title
    const titleFontSize = Math.max(28, canvas.width * 0.018);
    pdf.setTextColor(255, 255, 255);
    pdf.setFontSize(titleFontSize);
    pdf.text(reportTitle, 60, headerHeight * 0.6);

    // Timestamp
    const timeFontSize = Math.max(16, canvas.width * 0.011);
    pdf.setFontSize(timeFontSize);
    pdf.setTextColor(156, 163, 175);
    const timeStr = `Rapor Tarihi: ${new Date().toLocaleString('tr-TR')}`;
    
    // Calculate exact width of timestamp string to align it properly to the right
    const timeStrWidth = pdf.getStringUnitWidth(timeStr) * timeFontSize;
    pdf.text(timeStr, pdfWidth - timeStrWidth - 60, headerHeight * 0.6);

    // Add Image below header
    pdf.addImage(imgData, 'JPEG', 0, headerHeight, canvas.width, canvas.height);

    pdf.save(filename);
    return true;
  } catch (error) {
    console.error('PDF export failed:', error);
    return false;
  } finally {
    document.body.classList.remove('is-exporting');
  }
}
