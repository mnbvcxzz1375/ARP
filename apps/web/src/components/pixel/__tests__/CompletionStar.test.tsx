import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { UserPreferences } from '../../../hooks/usePreferences';

// useCompletionBurst (and thus PixelCopyButton) read the settings-center
// preference; mock the hook so no network query runs.
vi.mock('../../../hooks/usePreferences', () => ({
  usePreferences: vi.fn(),
}));

import { usePreferences } from '../../../hooks/usePreferences';
import { CompletionStar } from '../CompletionStar';
import { useCompletionBurst } from '../useCompletionBurst';
import {
  FilterPill,
  PIX_LINK_PRIMARY,
  PixelCopyButton,
  PixButton,
  PRESS_FEEDBACK,
} from '../../../features/connections/pixel-ui';

// ---------------------------------------------------------------------------
// Environment stubs (jsdom has no matchMedia; the design rules gate every
// JS timer on the reduced-motion media query)
// ---------------------------------------------------------------------------

let reducedMotionMedia = false;

function installMatchMedia() {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? reducedMotionMedia : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function mockPreferences(overrides?: Partial<UserPreferences>) {
  vi.mocked(usePreferences).mockReturnValue({
    data: {
      locale: null,
      theme: null,
      fontScale: null,
      reducedMotion: null,
      ...overrides,
    },
    isLoading: false,
    isError: false,
    isSaving: false,
    saveError: null,
    patchPreferences: vi.fn(),
  });
}

function mockClipboard(writeText: () => Promise<void>) {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
  });
}

beforeEach(() => {
  reducedMotionMedia = false;
  installMatchMedia();
  mockPreferences();
  mockClipboard(() => Promise.resolve());
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Harness for the hook (drives CompletionStar exactly like JourneyMap will)
// ---------------------------------------------------------------------------

function BurstHarness({ status }: { status: string }) {
  const { burst, ack } = useCompletionBurst(status);
  return (
    <>
      <div data-testid="burst-state">{String(burst)}</div>
      <CompletionStar burst={burst} onDone={ack} />
    </>
  );
}

// ---------------------------------------------------------------------------
// 1. Press feedback on buttons / links
// ---------------------------------------------------------------------------

describe('press feedback', () => {
  it('PixButton sinks 2px while pressed', () => {
    render(<PixButton>Deploy</PixButton>);
    const button = screen.getByRole('button', { name: 'Deploy' });
    expect(button.className).toContain(PRESS_FEEDBACK);
    expect(button.className).toContain('active:translate-y-[2px]');
  });

  it('FilterPill sinks 2px while pressed', () => {
    render(<FilterPill active={false}>All</FilterPill>);
    const pill = screen.getByRole('button', { name: 'All' });
    expect(pill.className).toContain('active:translate-y-[2px]');
  });

  it('PIX_LINK_PRIMARY is a plain anchor class (no a > button nesting)', () => {
    render(
      <a href="/docs/quickstart" className={PIX_LINK_PRIMARY}>
        Read the quickstart
      </a>,
    );
    const link = screen.getByRole('link', { name: 'Read the quickstart' });
    expect(link.tagName).toBe('A');
    expect(link.className).toContain('bg-pixel-accent');
    expect(link.className).toContain('min-h-[44px]');
    expect(link.className).toContain('active:translate-y-[2px]');
  });
});

// ---------------------------------------------------------------------------
// 2. PixelCopyButton
// ---------------------------------------------------------------------------

describe('PixelCopyButton', () => {
  it('shows the check and Copied label after a successful copy', async () => {
    const writeText = vi.fn(() => Promise.resolve());
    mockClipboard(writeText);

    render(<PixelCopyButton text="api-key-123" />);
    fireEvent.click(screen.getByRole('button'));

    expect(writeText).toHaveBeenCalledWith('api-key-123');
    expect(await screen.findByText('Copied')).toBeInTheDocument();
    expect(screen.getByRole('button').querySelector('.lucide-check')).not.toBeNull();
    expect(screen.getByRole('button').querySelector('.lucide-copy')).toBeNull();
    // Success path never announces a failure.
    expect(screen.queryByText('Copy failed')).toBeNull();
  });

  it('rolls back to the copy label after 1200ms', async () => {
    vi.useFakeTimers();
    render(<PixelCopyButton text="api-key-123" />);
    fireEvent.click(screen.getByRole('button'));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText('Copied')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1200);
    });
    expect(screen.getByText('Copy')).toBeInTheDocument();
    expect(screen.queryByText('Copied')).toBeNull();
  });

  it('never fakes success when the clipboard rejects', async () => {
    mockClipboard(() => Promise.reject(new Error('permission denied')));

    render(<PixelCopyButton text="api-key-123" />);
    fireEvent.click(screen.getByRole('button'));
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.queryByText('Copied')).toBeNull();
    expect(screen.getByRole('button').querySelector('.lucide-check')).toBeNull();
    // aria-live="polite" announces the failure instead.
    expect(screen.getByText('Copy failed')).toBeInTheDocument();
  });

  it('announces failure when the clipboard API is unavailable', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });

    render(<PixelCopyButton text="api-key-123" />);
    fireEvent.click(screen.getByRole('button'));
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.queryByText('Copied')).toBeNull();
    expect(screen.getByText('Copy failed')).toBeInTheDocument();
  });

  it('shows no check under the reduced-motion media query', async () => {
    reducedMotionMedia = true;
    installMatchMedia();

    render(<PixelCopyButton text="api-key-123" />);
    fireEvent.click(screen.getByRole('button'));
    await act(async () => {
      await Promise.resolve();
    });

    // Terminal state: Copy icon/label stay; the success check never appears.
    expect(screen.getByText('Copy')).toBeInTheDocument();
    expect(screen.queryByText('Copied')).toBeNull();
    expect(screen.getByRole('button').querySelector('.lucide-check')).toBeNull();
  });

  it('keeps the 44px touch target', () => {
    render(<PixelCopyButton text="api-key-123" />);
    const button = screen.getByRole('button');
    expect(button.className).toContain('min-h-[44px]');
    expect(button.className).toContain('min-w-[44px]');
  });
});

// ---------------------------------------------------------------------------
// 3. CompletionStar component
// ---------------------------------------------------------------------------

describe('CompletionStar', () => {
  it('renders nothing when the burst is not armed', () => {
    render(<CompletionStar burst={false} onDone={vi.fn()} />);
    expect(document.querySelector('svg.completion-star')).toBeNull();
  });

  it('renders the pixel star while armed and unmounts when ack clears the burst', () => {
    const onDone = vi.fn();
    const { rerender } = render(<CompletionStar burst={true} onDone={onDone} />);
    const star = document.querySelector('svg.completion-star');
    expect(star).not.toBeNull();

    fireEvent.animationEnd(star as Element);
    expect(onDone).toHaveBeenCalledTimes(1);
    // The parent (ack) flips the prop; the component itself is presentational.
    rerender(<CompletionStar burst={false} onDone={onDone} />);
    expect(document.querySelector('svg.completion-star')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 4. useCompletionBurst hook (via the harness)
// ---------------------------------------------------------------------------

describe('useCompletionBurst', () => {
  it('fires only on a non-completed -> completed migration', () => {
    const { rerender } = render(<BurstHarness status="running" />);
    expect(screen.getByTestId('burst-state').textContent).toBe('false');

    rerender(<BurstHarness status="completed" />);
    expect(screen.getByTestId('burst-state').textContent).toBe('true');
    expect(document.querySelector('svg.completion-star')).not.toBeNull();

    // ack() (wired to onAnimationEnd) unmounts the star.
    fireEvent.animationEnd(document.querySelector('svg.completion-star') as Element);
    expect(screen.getByTestId('burst-state').textContent).toBe('false');
    expect(document.querySelector('svg.completion-star')).toBeNull();
  });

  it('never re-arms while staying on completed', () => {
    const { rerender } = render(<BurstHarness status="completed" />);
    expect(screen.getByTestId('burst-state').textContent).toBe('false');

    rerender(<BurstHarness status="completed" />);
    expect(screen.getByTestId('burst-state').textContent).toBe('false');
  });

  it('does not fire for non-completed transitions', () => {
    const { rerender } = render(<BurstHarness status="queued" />);
    rerender(<BurstHarness status="delivering" />);
    rerender(<BurstHarness status="failed" />);
    expect(screen.getByTestId('burst-state').textContent).toBe('false');
    expect(document.querySelector('svg.completion-star')).toBeNull();
  });

  it('clears a stuck burst with the 2200ms fallback ack', () => {
    vi.useFakeTimers();
    const { rerender } = render(<BurstHarness status="running" />);
    rerender(<BurstHarness status="completed" />);
    expect(screen.getByTestId('burst-state').textContent).toBe('true');

    // onAnimationEnd never fires (killed CSS animation); the fallback still
    // clears the burst so the star cannot linger as a static node.
    act(() => {
      vi.advanceTimersByTime(2200);
    });
    expect(screen.getByTestId('burst-state').textContent).toBe('false');
    expect(document.querySelector('svg.completion-star')).toBeNull();
  });

  it('stays false under the reduced-motion media query', () => {
    reducedMotionMedia = true;
    installMatchMedia();

    const { rerender } = render(<BurstHarness status="running" />);
    rerender(<BurstHarness status="completed" />);
    expect(screen.getByTestId('burst-state').textContent).toBe('false');
    expect(document.querySelector('svg.completion-star')).toBeNull();
  });

  it('stays false when the user manually enabled reduced motion', () => {
    mockPreferences({ reducedMotion: true });

    const { rerender } = render(<BurstHarness status="running" />);
    rerender(<BurstHarness status="completed" />);
    expect(screen.getByTestId('burst-state').textContent).toBe('false');
  });
});
