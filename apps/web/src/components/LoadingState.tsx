import { Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';

export default function LoadingState({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center justify-center p-12', className)}>
      <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
    </div>
  );
}
