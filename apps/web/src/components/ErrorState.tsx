import { AlertTriangle } from 'lucide-react';

export default function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-red-600">
      <AlertTriangle className="h-10 w-10 mb-3" />
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}
