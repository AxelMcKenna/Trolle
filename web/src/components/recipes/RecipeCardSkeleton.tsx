import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export const RecipeCardSkeleton = () => {
  return (
    <Card className="p-4 bg-card h-full flex flex-col">
      {/* Image placeholder */}
      <Skeleton className="w-full h-36 rounded-md mb-3" />
      {/* Title */}
      <Skeleton className="h-4 w-3/4 mb-1" />
      {/* Description */}
      <Skeleton className="h-3 w-full mb-1" />
      <Skeleton className="h-3 w-2/3 mb-3 flex-1" />
      {/* Badges */}
      <div className="flex items-center gap-2 mt-auto">
        <Skeleton className="h-5 w-14 rounded-full" />
        <Skeleton className="h-5 w-24 rounded-full" />
      </div>
    </Card>
  );
};
