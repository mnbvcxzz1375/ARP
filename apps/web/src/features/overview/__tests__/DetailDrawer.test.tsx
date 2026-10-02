import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DetailDrawer from '../DetailDrawer';
import { useState } from 'react';

/** Renders a trigger button + the drawer; `rerender` toggles `open` while
 *  keeping the same trigger element (the focus-return assertion needs a
 *  stable node across the open/close transition). */
function setup(open: boolean) {
  const onClose = vi.fn();
  const tree = (next: boolean) => (
    <div>
      <button type="button">Island A</button>
      <DetailDrawer open={next} onClose={onClose} title="Agent details">
        <p>Panel body</p>
      </DetailDrawer>
    </div>
  );
  const { rerender } = render(tree(open));
  const toggle = (next: boolean) => rerender(tree(next));
  return { onClose, toggle, trigger: screen.getByRole('button', { name: 'Island A' }) };
}

describe('DetailDrawer', () => {
  it('returns focus when the overview conditionally unmounts the open drawer', () => {
    function Host() {
      const [open, setOpen] = useState(false);
      return <>
        <button onClick={() => setOpen(true)}>Open island</button>
        {open && <DetailDrawer open onClose={() => setOpen(false)}><p>Details</p></DetailDrawer>}
      </>;
    }
    render(<Host />);
    const trigger = screen.getByRole('button', { name: 'Open island' });
    trigger.focus();
    fireEvent.click(trigger);
    fireEvent.keyDown(screen.getByRole('button', { name: 'Close agent details' }), { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it('wraps keyboard focus inside the open modal', () => {
    render(<DetailDrawer open onClose={vi.fn()}><a href="/app/agents">Agent page</a></DetailDrawer>);
    const last = screen.getByRole('link', { name: 'Agent page' });
    last.focus();
    fireEvent.keyDown(last, { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'Close agent details' })).toHaveFocus();
  });

  it('renders nothing while closed', () => {
    setup(false);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders the dialog with a title and close button while open', () => {
    setup(true);
    expect(screen.getByRole('dialog', { name: 'Agent details' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close agent details' })).toBeInTheDocument();
    expect(screen.getByText('Panel body')).toBeInTheDocument();
  });

  // A11y contract #1: Escape closes the drawer.
  it('closes on Escape', () => {
    const { onClose } = setup(true);
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes via the close button and the scrim click', () => {
    const { onClose } = setup(true);
    const dialog = screen.getByRole('dialog');
    // The scrim is the inert layer placed right before the dialog in the
    // fixed overlay.
    const scrim = dialog.previousElementSibling as HTMLElement;
    expect(scrim).not.toBeNull();

    fireEvent.click(scrim);
    fireEvent.click(screen.getByRole('button', { name: 'Close agent details' }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  // A11y contract #2: opening lands focus inside the dialog (on the close
  // button) instead of leaving the keyboard user on the page behind it.
  it('moves focus to the close button on open', () => {
    setup(true);
    expect(screen.getByRole('button', { name: 'Close agent details' })).toHaveFocus();
  });

  // A11y contract #3: closing returns focus to the trigger node (the
  // island button that had focus when the drawer opened). The focus
  // checks only pass because jsdom tracks real focus state.
  it('returns focus to the trigger node when it closes', () => {
    const { toggle, trigger } = setup(false);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    toggle(true);
    expect(screen.getByRole('button', { name: 'Close agent details' })).toHaveFocus();

    toggle(false);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  // The overview page composes the drawer with an embedded panel whose
  // own header is the visible title; without an explicit `title` the
  // drawer still needs an accessible name and the close bar.
  it('falls back to the default accessible title when none is passed', () => {
    const { rerender } = render(
      <DetailDrawer open={true} onClose={vi.fn()}>
        <p>Panel body</p>
      </DetailDrawer>,
    );
    expect(screen.getByRole('dialog', { name: 'Agent details' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close agent details' })).toBeInTheDocument();
    // The visible title text is suppressed (the panel header carries it).
    expect(screen.queryByRole('heading')).toBeNull();
    rerender(
      <DetailDrawer open={false} onClose={vi.fn()}>
        <p>Panel body</p>
      </DetailDrawer>,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
