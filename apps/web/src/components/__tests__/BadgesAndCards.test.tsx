import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import RiskBadge from '../RiskBadge';
import RoleBadge from '../RoleBadge';
import StatCard from '../StatCard';
import Pagination from '../Pagination';
import { vi } from 'vitest';

describe('RiskBadge', () => {
  it('renders low risk', () => {
    render(<RiskBadge level="low" />);
    const badge = screen.getByText('low');
    expect(badge.className).toContain('bg-pixel-led-green');
  });

  it('renders medium risk', () => {
    render(<RiskBadge level="medium" />);
    const badge = screen.getByText('medium');
    expect(badge.className).toContain('bg-pixel-led-amber');
  });

  it('renders high risk', () => {
    render(<RiskBadge level="high" />);
    const badge = screen.getByText('high');
    expect(badge.className).toContain('bg-pixel-led-red');
  });

  it('renders critical risk', () => {
    render(<RiskBadge level="critical" />);
    expect(screen.getByText('critical')).toBeInTheDocument();
  });
});

describe('RoleBadge', () => {
  it('renders user role', () => {
    render(<RoleBadge role="user" />);
    const badge = screen.getByText('user');
    expect(badge.className).toContain('bg-pixel-accent-2');
  });

  it('renders admin role', () => {
    render(<RoleBadge role="admin" />);
    const badge = screen.getByText('admin');
    expect(badge.className).toContain('bg-pixel-accent');
  });

  it('renders super_admin role', () => {
    render(<RoleBadge role="super_admin" />);
    const badge = screen.getByText('super admin');
    // Role is identity, not status: neutral chip, never the LED-red status color.
    expect(badge.className).toContain('bg-[#4b4968]');
    expect(badge.className).not.toContain('bg-pixel-led-red');
  });

  it('formats underscores as spaces', () => {
    render(<RoleBadge role="super_admin" />);
    expect(screen.getByText('super admin')).toBeInTheDocument();
  });
});

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard label="Active Agents" value={42} />);
    expect(screen.getByText('Active Agents')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders danger variant', () => {
    render(<StatCard label="Errors" value={5} variant="danger" />);
    const card = screen.getByText('5').closest('div[class*="border"]');
    expect(card?.className).toContain('border');
  });
});

describe('Pagination', () => {
  it('renders nothing when only one page', () => {
    const { container } = render(
      <Pagination offset={0} limit={50} total={5} onPageChange={vi.fn()} />
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders page info for multiple pages', () => {
    render(<Pagination offset={0} limit={50} total={120} onPageChange={vi.fn()} />);
    expect(screen.getByText('Showing 1-50 of 120')).toBeInTheDocument();
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('calls onPageChange when Prev clicked', () => {
    const onChange = vi.fn();
    render(<Pagination offset={50} limit={50} total={120} onPageChange={onChange} />);
    screen.getByText('Prev').click();
    expect(onChange).toHaveBeenCalledWith(0);
  });

  it('calls onPageChange when Next clicked', () => {
    const onChange = vi.fn();
    render(<Pagination offset={0} limit={50} total={120} onPageChange={onChange} />);
    screen.getByText('Next').click();
    expect(onChange).toHaveBeenCalledWith(50);
  });

  it('disables Prev on first page', () => {
    render(<Pagination offset={0} limit={50} total={120} onPageChange={vi.fn()} />);
    expect(screen.getByText('Prev')).toBeDisabled();
  });

  it('disables Next on last page', () => {
    render(<Pagination offset={100} limit={50} total={120} onPageChange={vi.fn()} />);
    expect(screen.getByText('Next')).toBeDisabled();
  });
});
