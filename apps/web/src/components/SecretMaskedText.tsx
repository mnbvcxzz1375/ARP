import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

const SECRET_PATTERNS = [
  /sk-[A-Za-z0-9]{20,}/g,
  /agt_sk_[A-Za-z0-9_-]{20,}/g,
  /ak_[A-Za-z0-9]{20,}/g,
];

export default function SecretMaskedText({ text, className }: { text: string; className?: string }) {
  const [visible, setVisible] = useState(false);

  if (!text) return null;

  let masked = text;
  if (!visible) {
    for (const pattern of SECRET_PATTERNS) {
      masked = masked.replace(pattern, '***');
    }
  }

  return (
    <div className={`flex items-center gap-2 ${className || ''}`}>
      <code className="text-xs bg-gray-100 px-2 py-1 rounded break-all flex-1">{masked}</code>
      <button onClick={() => setVisible(!visible)} className="text-gray-400 hover:text-gray-600">
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}
