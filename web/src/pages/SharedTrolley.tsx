import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ShoppingCart, ArrowLeft, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useTrolleyContext } from '@/contexts/TrolleyContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

interface SharedTrolleyData {
  id: string;
  name: string;
  items: Array<{
    product_id: string;
    name: string;
    brand?: string | null;
    size?: string | null;
    chain: string;
    image_url?: string | null;
    quantity: number;
  }>;
  item_count: number;
}

export const SharedTrolley = () => {
  const { token } = useParams<{ token: string }>();
  const [trolley, setTrolley] = useState<SharedTrolleyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const { addItems } = useTrolleyContext();

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    api.get<SharedTrolleyData>(`/trolleys/shared/${token}`)
      .then((res) => setTrolley(res.data))
      .catch(() => setError('Shared trolley not found'))
      .finally(() => setLoading(false));
  }, [token]);

  const handleClone = () => {
    if (!trolley) return;
    const added = addItems(trolley.items.map((item) => ({
      product_id: item.product_id,
      name: item.name,
      brand: item.brand,
      size: item.size,
      chain: item.chain,
      image_url: item.image_url,
    })));
    if (added === 0) {
      toast.info('All items already in your trolley');
    }
  };

  const handleCopyLink = async () => {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    toast.success('Link copied');
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-secondary">
        <div className="max-w-2xl mx-auto px-4 py-12">
          <Skeleton className="h-8 w-48 mb-4" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      </div>
    );
  }

  if (error || !trolley) {
    return (
      <div className="min-h-screen bg-secondary flex items-center justify-center">
        <Card className="p-8 text-center max-w-md">
          <ShoppingCart className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Trolley not found</h2>
          <p className="text-sm text-muted-foreground mb-4">This shared trolley may have been removed.</p>
          <Link to="/"><Button>Go Home</Button></Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary">
      <div className="bg-primary text-white px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <Link to="/" className="text-lg font-semibold">TROLL-E</Link>
          <Link to="/trolley">
            <Button variant="ghost" size="sm" className="text-white hover:bg-white/10">
              <ShoppingCart className="h-4 w-4 mr-1" />My Trolley
            </Button>
          </Link>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" />Back
        </Link>

        <Card className="p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-xl font-semibold">{trolley.name}</h1>
            <span className="text-sm text-muted-foreground">{trolley.item_count} items</span>
          </div>

          <div className="space-y-2">
            {trolley.items.map((item) => (
              <div key={item.product_id} className="flex items-center gap-3 p-2 bg-secondary rounded-lg">
                {item.image_url ? (
                  <img src={item.image_url} alt={item.name} className="w-10 h-10 object-cover rounded" />
                ) : (
                  <div className="w-10 h-10 bg-muted rounded flex items-center justify-center">
                    <ShoppingCart className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.name}</p>
                  <p className="text-xs text-muted-foreground">{item.chain} {item.size ? `· ${item.size}` : ''}</p>
                </div>
                <span className="text-xs text-muted-foreground">x{item.quantity}</span>
              </div>
            ))}
          </div>
        </Card>

        <div className="flex gap-2">
          <Button onClick={handleClone} className="flex-1">
            <ShoppingCart className="h-4 w-4 mr-2" />Clone to My Trolley
          </Button>
          <Button variant="outline" onClick={handleCopyLink}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SharedTrolley;
