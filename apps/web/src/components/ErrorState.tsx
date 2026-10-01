import { AlertTriangle } from 'lucide-react';

export default function ErrorState({ message }: { message: string }) {
  // Theme-safe error contrast: bg-pixel-surface is a theme variable
  // (#222034 dark / #eef1fa light), so neither the icon nor the message
  // can rely on a single text color (red-as-text fails AA in at least one
  // theme; #ac3232 on #222034 is 2.46:1, on #eef1fa it passes but
  // red-400 on #eef1fa is 2.45:1). Both the glyph tile and the message
  // are solid LED-red chips with light text: ~5.9:1 in BOTH themes.
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-12 bg-pixel-surface border-2 border-pixel-led-red">
      <span className="inline-flex items-center justify-center w-12 h-12 bg-pixel-led-red">
        <AlertTriangle className="w-8 h-8 text-[#f4f4fa]" strokeWidth={2} aria-hidden="true" />
      </span>
      <p className="px-3 py-1 text-base font-pixel bg-pixel-led-red text-[#f4f4fa]">
        {message}
      </p>
    </div>
  );
}
