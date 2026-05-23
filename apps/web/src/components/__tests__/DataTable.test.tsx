import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import DataTable from '../DataTable';

interface TestItem {
  id: string;
  name: string;
  value: number;
}

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Name' },
  { key: 'value', label: 'Value', render: (row: TestItem) => <strong>{row.value}</strong> },
];

const data: TestItem[] = [
  { id: '1', name: 'Alpha', value: 10 },
  { id: '2', name: 'Beta', value: 20 },
];

describe('DataTable', () => {
  it('renders column headers', () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText('ID')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Value')).toBeInTheDocument();
  });

  it('renders data rows', () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('renders custom cell renderers', () => {
    render(<DataTable columns={columns} data={data} />);
    const strongEl = screen.getByText('10');
    expect(strongEl.tagName).toBe('STRONG');
  });

  it('shows "No data" message for empty data', () => {
    render(<DataTable columns={columns} data={[]} />);
    expect(screen.getByText('No data')).toBeInTheDocument();
  });
});
