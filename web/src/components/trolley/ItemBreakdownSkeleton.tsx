import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export const ItemBreakdownSkeleton = () => {
  return (
    <Card className="bg-card overflow-hidden">
      {/* Store header */}
      <div className="p-4 border-b bg-secondary/50">
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-5 rounded-full" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>
      {/* Department header */}
      <div className="px-3 py-1.5 bg-secondary/70 border-y">
        <Skeleton className="h-3 w-20" />
      </div>
      {/* Item rows */}
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="p-3 flex items-center gap-3 border-b last:border-0">
          <Skeleton className="w-10 h-10 rounded flex-shrink-0" />
          <div className="flex-1 min-w-0 space-y-1.5">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="h-4 w-12 flex-shrink-0" />
        </div>
      ))}
      {/* Footer */}
      <div className="p-4 border-t bg-secondary/50">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-6 w-16" />
        </div>
      </div>
    </Card>
  );
};
