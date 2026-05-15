import { useEffect, useRef, useCallback } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import { X } from 'lucide-react';

interface BarcodeScannerProps {
  isOpen: boolean;
  onScan: (barcode: string) => void;
  onClose: () => void;
}

const SCANNER_REGION_ID = 'barcode-scanner-region';

export const BarcodeScanner = ({ isOpen, onScan, onClose }: BarcodeScannerProps) => {
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const hasScannedRef = useRef(false);

  const stopScanner = useCallback(async () => {
    if (scannerRef.current) {
      try {
        const state = scannerRef.current.getState();
        if (state === 2) { // SCANNING
          await scannerRef.current.stop();
        }
      } catch {
        // scanner may already be stopped
      }
      scannerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;

    hasScannedRef.current = false;
    let mounted = true;

    const startScanner = async () => {
      // Small delay to ensure DOM element is rendered
      await new Promise((r) => setTimeout(r, 100));
      if (!mounted) return;

      const scanner = new Html5Qrcode(SCANNER_REGION_ID);
      scannerRef.current = scanner;

      try {
        await scanner.start(
          { facingMode: 'environment' },
          {
            fps: 10,
            qrbox: { width: 280, height: 150 },
            aspectRatio: 1.5,
          },
          (decodedText) => {
            if (!hasScannedRef.current) {
              hasScannedRef.current = true;
              onScan(decodedText);
            }
          },
          () => {
            // ignore scan failures (no barcode in frame)
          },
        );
      } catch {
        // Camera permission denied or not available
      }
    };

    startScanner();

    return () => {
      mounted = false;
      stopScanner();
    };
  }, [isOpen, onScan, stopScanner]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-sm overflow-hidden shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h3 className="text-sm font-semibold">Scan a barcode</h3>
          <button
            onClick={() => {
              stopScanner();
              onClose();
            }}
            className="p-1 hover:bg-secondary rounded-md transition-colors"
            aria-label="Close scanner"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-4">
          <div
            id={SCANNER_REGION_ID}
            className="w-full rounded-lg overflow-hidden"
          />
          <p className="text-xs text-muted-foreground text-center mt-3">
            Point your camera at a product barcode
          </p>
        </div>
      </div>
    </div>
  );
};
