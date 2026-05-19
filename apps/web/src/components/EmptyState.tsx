import { Inbox } from 'lucide-react';

export default function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-gray-500">
      <Inbox className="h-10 w-10 mb-3" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
