import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export const StoreRankSkeleton = () => {
  return (
    <Card className="p-3 bg-card">
      <div className="flex items-center gap-3">
        {/* Rank */}
        <Skeleton className="w-6 h-4 flex-shrink-0" />
        {/* Chain logo */}
        <Skeleton className="h-6 w-6 rounded-full flex-shrink-0" />
        {/* Store info */}
        <div className="flex-1 min-w-0 space-y-1.5">
          <Skeleton className="h-4 w-2/3" />
          <div className="flex items-center gap-3">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-4 w-16 rounded-full" />
          </div>
        </div>
        {/* Price */}
        <Skeleton className="h-6 w-16 flex-shrink-0" />
        {/* Chevron */}
        <Skeleton className="h-4 w-4 flex-shrink-0" />
      </div>
    </Card>
  );
};
