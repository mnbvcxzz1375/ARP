import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import RelayLighthouse, { LIGHTHOUSE_DEFAULT_POSITION } from '../RelayLighthouse';

afterEach(cleanup);
describe('RelayLighthouse', () => {
  it('preserves the stage anchor and accepts a caller-provided position', () => {
    const { container, rerender } = render(<RelayLighthouse />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.style.left).toBe('480px');
    expect(root.style.top).toBe('346px');
    expect(root.style.transform).toBe('translate(-50%, -50%)');
    expect(LIGHTHOUSE_DEFAULT_POSITION).toEqual({ x: 480, y: 346 });
    rerender(<RelayLighthouse position={{ x: 100, y: 200 }} />);
    expect(root.style.left).toBe('100px');
    expect(root.style.top).toBe('200px');
  });

  it('keeps the scene landmark decorative and out of the keyboard and screen-reader sequence', () => {
    const { container } = render(<RelayLighthouse />);
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
    expect(container.querySelector('img')).toHaveAttribute('alt', '');
  });
});
