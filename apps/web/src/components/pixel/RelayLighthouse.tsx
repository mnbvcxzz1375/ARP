/** Central scene landmark. Raster artwork is separate from business state. */
export const LIGHTHOUSE_DEFAULT_POSITION = { x: 480, y: 346 } as const;

export interface RelayLighthouseProps {
  position?: { x: number; y: number };
  className?: string;
}

export default function RelayLighthouse({
  position = LIGHTHOUSE_DEFAULT_POSITION,
  className,
}: RelayLighthouseProps) {
  return (
    <div
      className={['relay-lighthouse', className].filter(Boolean).join(' ')}
      style={{
        left: position.x + 'px',
        top: position.y + 'px',
        transform: 'translate(-50%, -50%)',
      }}
      role="presentation"
      aria-hidden="true"
    >
      <img
        src="/art/archipelago/relay-lighthouse.png"
        alt=""
        className="relay-lighthouse__art"
        width={360}
        height={360}
        draggable={false}
      />
      <span className="relay-lighthouse__label">AGENTNET / RELAY</span>
    </div>
  );
}
