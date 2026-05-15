import { useState, useCallback } from 'react';
import { ScanBarcode } from 'lucide-react';
import { BarcodeScanner } from './BarcodeScanner';

interface BarcodeScanButtonProps {
  onScan: (barcode: string) => void;
  className?: string;
}

export const BarcodeScanButton = ({ onScan, className = '' }: BarcodeScanButtonProps) => {
  const [scannerOpen, setScannerOpen] = useState(false);

  const handleScan = useCallback(
    (barcode: string) => {
      setScannerOpen(false);
      onScan(barcode);
    },
    [onScan],
  );

  return (
    <>
      <button
        onClick={() => setScannerOpen(true)}
        className={`p-2 hover:bg-secondary/50 rounded-md transition-colors ${className}`}
        aria-label="Scan barcode"
        title="Scan barcode"
      >
        <ScanBarcode className="h-4 w-4 text-muted-foreground" />
      </button>
      <BarcodeScanner
        isOpen={scannerOpen}
        onScan={handleScan}
        onClose={() => setScannerOpen(false)}
      />
    </>
  );
};
