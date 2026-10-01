import { Inbox } from 'lucide-react';

export default function EmptyState({ message }: { message: string }) {
  // Self-contained panel so muted text keeps contrast on any page surface.
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-12 bg-pixel-surface border-2 border-pixel-line">
      <Inbox className="w-10 h-10 text-pixel-muted" strokeWidth={2} aria-hidden="true" />
      <p className="text-base text-pixel-muted">{message}</p>
    </div>
  );
}
