import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import * as Sentry from "@sentry/react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider } from "@/contexts/AuthContext";
import { LocationProvider } from "@/contexts/LocationContext";
import { TrolleyProvider } from "@/contexts/TrolleyContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { LocationModal } from "@/components/location/LocationModal";
import { Toaster } from "sonner";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/react";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";

// Sentry error tracking (no-op if DSN not set)
const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
  });
}

// Lazy load route components for code splitting
const Landing = lazy(() => import("@/pages/Landing"));
const Explore = lazy(() => import("@/pages/Explore"));
const Trolley = lazy(() => import("@/pages/Trolley"));
const Recipes = lazy(() => import("@/pages/Recipes"));
const RecipeDetail = lazy(() => import("@/pages/RecipeDetail"));
const RecipeCreate = lazy(() => import("@/pages/RecipeCreate"));
const Login = lazy(() => import("@/pages/Login"));
const Signup = lazy(() => import("@/pages/Signup"));
const AuthCallback = lazy(() => import("@/pages/AuthCallback"));
const Account = lazy(() => import("@/pages/Account"));
const SharedTrolley = lazy(() => import("@/pages/SharedTrolley"));
const SharedRecipe = lazy(() => import("@/pages/SharedRecipe"));

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
        <AuthProvider>
          <LocationProvider>
            <TrolleyProvider>
            <LocationModal />
            <Toaster position="top-right" richColors closeButton />
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/explore" element={<Explore />} />
                <Route path="/trolley" element={<Trolley />} />
                <Route path="/recipes" element={<Recipes />} />
                <Route path="/recipes/create" element={<RecipeCreate />} />
                <Route path="/recipes/:id" element={<RecipeDetail />} />
                <Route path="/login" element={<Login />} />
                <Route path="/signup" element={<Signup />} />
                <Route path="/auth/callback" element={<AuthCallback />} />
                <Route path="/account" element={<ProtectedRoute><Account /></ProtectedRoute>} />
                <Route path="/trolley/shared/:token" element={<SharedTrolley />} />
                <Route path="/recipes/shared/:token" element={<SharedRecipe />} />
                <Route path="/product/:id" element={<Navigate to="/explore" replace />} />
              </Routes>
            </Suspense>
            </TrolleyProvider>
          </LocationProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
    <Analytics />
    <SpeedInsights />
  </React.StrictMode>
);
