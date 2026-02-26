import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { LocationProvider } from "@/contexts/LocationContext";
import { TrolleyProvider } from "@/contexts/TrolleyContext";
import { Toaster } from "sonner";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/react";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";

// Lazy load route components for code splitting
const Landing = lazy(() => import("@/pages/Landing"));
const Explore = lazy(() => import("@/pages/Explore"));
const Trolley = lazy(() => import("@/pages/Trolley"));

// Loading fallback component
const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center bg-white">
    <div className="text-center">
      <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
      <p className="text-gray-600">Loading...</p>
    </div>
  </div>
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <LocationProvider>
          <TrolleyProvider>
            <Toaster position="top-right" richColors closeButton />
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/explore" element={<Explore />} />
                <Route path="/trolley" element={<Trolley />} />
                <Route path="/product/:id" element={<Navigate to="/explore" replace />} />
              </Routes>
            </Suspense>
          </TrolleyProvider>
        </LocationProvider>
      </BrowserRouter>
    </ErrorBoundary>
    <Analytics />
    <SpeedInsights />
  </React.StrictMode>
);
