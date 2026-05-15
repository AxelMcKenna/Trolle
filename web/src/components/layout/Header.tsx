import { useState, useEffect, useRef, useCallback } from "react";
import { Search, MapPin, ShoppingCart, UtensilsCrossed, User, LogOut, Clock, X, Bell } from "lucide-react";
import { BarcodeScanButton } from "@/components/scanner/BarcodeScanButton";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useLocationContext } from "@/contexts/LocationContext";
import { useTrolleyContext } from "@/contexts/TrolleyContext";
import { useAuth } from "@/contexts/AuthContext";
import { useSearchHistory } from "@/hooks/useSearchHistory";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useNotifications } from "@/hooks/usePriceAlerts";

interface HeaderProps {
  query?: string;
  setQuery?: (query: string) => void;
  onSearch?: () => void;
  variant?: 'compact' | 'landing';
  showSearch?: boolean;
}

export const Header = ({
  query: externalQuery,
  setQuery: externalSetQuery,
  onSearch: externalOnSearch,
  variant = 'compact',
  showSearch = true,
}: HeaderProps) => {
  const [internalQuery, setInternalQuery] = useState('');
  const query = externalQuery ?? internalQuery;
  const setQuery = externalSetQuery ?? setInternalQuery;
  const { radiusKm, isLocationSet, openLocationModal } = useLocationContext();
  const { itemCount } = useTrolleyContext();
  const { isAuthenticated, user, displayName, signOut } = useAuth();
  const { notifications, fetchNotifications, markRead } = useNotifications();
  const navigate = useNavigate();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const { recentSearches, addSearch, clearHistory } = useSearchHistory();
  const searchContainerRef = useRef<HTMLDivElement>(null);

  // Poll for notifications every 60s when authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchNotifications();
    const interval = setInterval(() => fetchNotifications(), 60_000);
    return () => clearInterval(interval);
  }, [isAuthenticated, fetchNotifications]);

  // Close search history on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setSearchFocused(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleBarcodeScan = useCallback(async (barcode: string) => {
    // Try barcode lookup endpoint first
    try {
      const { data } = await api.get(`/products/barcode/${encodeURIComponent(barcode)}`);
      if (data?.id) {
        navigate(`/products/${data.id}`);
        return;
      }
    } catch {
      // No barcode match — fall back to text search
    }

    // Fallback: use barcode as search query
    setQuery(barcode);
    if (externalOnSearch) {
      setTimeout(() => externalOnSearch(), 0);
    } else {
      navigate(`/explore?q=${encodeURIComponent(barcode)}`);
    }
  }, [setQuery, externalOnSearch, navigate]);

  const handleSearchSubmit = () => {
    if (query.trim()) addSearch(query.trim());
    if (externalOnSearch) {
      externalOnSearch();
    } else {
      navigate(`/explore?q=${encodeURIComponent(query.trim())}`);
    }
    setSearchFocused(false);
  };

  // Close user menu on Escape key
  useEffect(() => {
    if (!userMenuOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setUserMenuOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [userMenuOpen]);

  if (variant === 'landing') {
    return (
      <header className="bg-primary border-b border-primary">
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="text-center">
            <h1 className="text-3xl md:text-4xl font-bold text-white mb-2 font-sans tracking-[0.15em]">
              TROLL-E
            </h1>
            <p className="text-sm text-white/80 mb-6">
              Compare grocery prices across NZ
            </p>
            <div className="max-w-xl mx-auto relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" aria-hidden="true" />
              <Input
                placeholder="Search for groceries..."
                aria-label="Search for groceries"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearchSubmit()}
                className="pl-12 pr-11 h-12 bg-white text-base"
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2">
                <BarcodeScanButton onScan={handleBarcodeScan} />
              </div>
            </div>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header className="bg-primary border-b border-primary">
      <div className="px-4 py-4">
        <div className="flex items-center justify-between gap-6">
          {/* Logo - hugs left edge */}
          <Link to="/" className="flex-shrink-0">
            <span className="text-lg font-bold text-white font-sans tracking-[0.15em]">TROLL-E</span>
          </Link>

          {/* Search - centered */}
          {showSearch && <div className="flex-1 flex justify-center">
            <div ref={searchContainerRef} className="relative w-full max-w-md">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <Input
                placeholder="Search products..."
                aria-label="Search products"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearchSubmit()}
                onFocus={() => setSearchFocused(true)}
                className="pl-10 pr-10 h-10 bg-white text-sm"
              />
              <div className="absolute right-1.5 top-1/2 -translate-y-1/2">
                <BarcodeScanButton onScan={handleBarcodeScan} />
              </div>
              {/* Recent searches dropdown — shows all when empty, filtered while typing */}
              {searchFocused && recentSearches.length > 0 && (() => {
                const filtered = query
                  ? recentSearches.filter((s) => s.toLowerCase().includes(query.toLowerCase()) && s.toLowerCase() !== query.toLowerCase())
                  : recentSearches;
                if (filtered.length === 0) return null;
                return (
                  <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg overflow-hidden">
                    <div className="flex items-center justify-between px-3 py-2 border-b">
                      <span className="text-xs font-medium text-muted-foreground">Recent searches</span>
                      <button onClick={clearHistory} className="text-xs text-muted-foreground hover:text-foreground">
                        Clear
                      </button>
                    </div>
                    {filtered.map((s) => (
                      <button
                        key={s}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-secondary/50 transition-colors"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          setQuery(s);
                          addSearch(s);
                          setSearchFocused(false);
                          if (externalOnSearch) {
                            // Defer so query state propagates before search fires
                            setTimeout(() => externalOnSearch(), 0);
                          } else {
                            navigate(`/explore?q=${encodeURIComponent(s)}`);
                          }
                        }}
                      >
                        <Clock className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        <span className="truncate">{s}</span>
                      </button>
                    ))}
                  </div>
                );
              })()}
            </div>
          </div>}
          {!showSearch && <div className="flex-1" />}

          {/* Right actions */}
          <div className="flex items-center gap-1 flex-shrink-0">
            <Link to="/recipes">
              <Button
                variant="ghost"
                size="sm"
                className="text-white hover:bg-white/10"
                aria-label="Recipes"
              >
                <UtensilsCrossed className="h-4 w-4" />
                <span className="hidden sm:inline ml-1">Recipes</span>
              </Button>
            </Link>
            <Link to="/trolley">
              <Button
                variant="ghost"
                size="sm"
                className="text-white hover:bg-white/10 relative"
                aria-label={`Trolley${itemCount > 0 ? ` (${itemCount} items)` : ''}`}
              >
                <ShoppingCart className="h-4 w-4" />
                {itemCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-white text-primary text-[10px] font-bold rounded-full h-4 min-w-[16px] flex items-center justify-center px-0.5" aria-hidden="true">
                    {itemCount}
                  </span>
                )}
              </Button>
            </Link>
            {isAuthenticated && (
              <div className="relative">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-white hover:bg-white/10 relative"
                  aria-label={`Notifications${notifications.unread_count > 0 ? ` (${notifications.unread_count} unread)` : ''}`}
                  onClick={() => setNotifOpen(!notifOpen)}
                >
                  <Bell className="h-4 w-4" />
                  {notifications.unread_count > 0 && (
                    <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full h-4 min-w-[16px] flex items-center justify-center px-0.5">
                      {notifications.unread_count}
                    </span>
                  )}
                </Button>
                {notifOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setNotifOpen(false)} />
                    <div className="absolute right-0 top-full mt-1 w-72 bg-white rounded-lg shadow-lg border z-50 overflow-hidden">
                      <div className="flex items-center justify-between px-3 py-2 border-b">
                        <span className="text-sm font-semibold text-gray-900">Notifications</span>
                        {notifications.unread_count > 0 && (
                          <button
                            onClick={() => markRead()}
                            className="text-xs text-primary hover:underline"
                          >
                            Mark all read
                          </button>
                        )}
                      </div>
                      <div className="max-h-64 overflow-y-auto">
                        {notifications.items.length === 0 ? (
                          <div className="px-3 py-6 text-center text-sm text-gray-400">
                            No notifications yet
                          </div>
                        ) : (
                          notifications.items.map((n) => (
                            <div
                              key={n.id}
                              className={`px-3 py-2.5 border-b last:border-0 ${!n.is_read ? 'bg-primary/5' : ''}`}
                            >
                              <p className="text-sm font-medium text-gray-900">{n.title}</p>
                              <p className="text-xs text-gray-500 mt-0.5">{n.message}</p>
                              <p className="text-[10px] text-gray-400 mt-1">
                                {new Date(n.created_at).toLocaleDateString()}
                              </p>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={openLocationModal}
              className="text-white hover:bg-white/10 gap-2"
              aria-label={isLocationSet ? `Location: ${radiusKm} km radius` : 'Set location'}
            >
              <MapPin className="h-4 w-4" />
              <span className="hidden sm:inline">
                {isLocationSet ? `${radiusKm} km` : 'Location'}
              </span>
            </Button>

            {/* User menu */}
            {isAuthenticated ? (
              <div className="relative">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-white hover:bg-white/10"
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  aria-label="User menu"
                  aria-expanded={userMenuOpen}
                >
                  <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center text-xs font-bold">
                    {(displayName?.[0] ?? user?.email?.[0] ?? "U").toUpperCase()}
                  </div>
                </Button>
                {userMenuOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />
                    <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-lg border z-50 py-1">
                      <div className="px-3 py-2 border-b">
                        {displayName && (
                          <p className="text-sm font-medium text-gray-900 truncate">{displayName}</p>
                        )}
                        <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                      </div>
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-gray-50 flex items-center gap-2"
                        onClick={() => { setUserMenuOpen(false); navigate("/account"); }}
                      >
                        <User className="h-3.5 w-3.5" /> Account
                      </button>
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-gray-50 flex items-center gap-2 text-red-600"
                        onClick={() => { setUserMenuOpen(false); signOut(); }}
                      >
                        <LogOut className="h-3.5 w-3.5" /> Sign Out
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <Link to="/login">
                <Button variant="ghost" size="sm" className="text-white hover:bg-white/10">
                  Sign In
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
