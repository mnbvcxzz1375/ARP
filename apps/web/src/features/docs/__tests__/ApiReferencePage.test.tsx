import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import ApiReferencePage from '../ApiReferencePage';
import {
  OPENAPI_SPEC,
  collectOpenApiOperations,
  type OpenApiSpec,
} from '../docsRegistry';

/** Reduced OpenAPI fragment (same shape as the committed artifact). */
const FRAGMENT: OpenApiSpec = {
  paths: {
    '/v1/widgets': {
      get: {
        tags: ['widgets'],
        summary: 'List widgets',
        description: 'List all registered widgets.',
        parameters: [
          {
            name: 'page',
            in: 'query',
            required: false,
            description: 'Page number',
            schema: { type: 'integer', format: 'int32' },
          },
          {
            name: 'status',
            in: 'query',
            required: true,
            description: 'Filter by status',
            schema: { type: 'string', enum: ['active', 'archived'] },
          },
        ],
      },
      post: {
        tags: ['widgets'],
        summary: 'Create widget',
        parameters: [],
      },
    },
    '/v1/health': {
      get: {
        tags: ['health'],
        summary: 'Service health',
        parameters: [],
      },
    },
  },
};

describe('ApiReferencePage', () => {
  it('groups endpoints by OpenAPI tag and orders by the known tag order', () => {
    render(<ApiReferencePage spec={FRAGMENT} />);

    // 'health' is a known tag and sorts before the unknown 'widgets'.
    const groups = screen.getAllByTestId('docs-api-tag-group');
    expect(groups.map((g) => g.getAttribute('data-tag'))).toEqual([
      'health',
      'widgets',
    ]);
  });

  it('renders method badges, paths, summaries and descriptions', () => {
    render(<ApiReferencePage spec={FRAGMENT} />);

    const widgetsGroup = screen
      .getAllByTestId('docs-api-tag-group')
      .find((g) => g.getAttribute('data-tag') === 'widgets');
    expect(widgetsGroup).toBeDefined();

    const endpoints = within(widgetsGroup!).getAllByTestId('docs-api-endpoint');
    expect(endpoints).toHaveLength(2);

    expect(within(endpoints[0]).getByText('GET')).toBeVisible();
    expect(within(endpoints[0]).getByText('/v1/widgets')).toBeVisible();
    expect(within(endpoints[0]).getByText('List widgets')).toBeVisible();
    expect(within(endpoints[0]).getByText('List all registered widgets.')).toBeVisible();

    expect(within(endpoints[1]).getByText('POST')).toBeVisible();
    expect(within(endpoints[1]).getByText('Create widget')).toBeVisible();
  });

  it('renders the parameter table with required flags and no-parameters note', () => {
    render(<ApiReferencePage spec={FRAGMENT} />);

    const widgetsGroup = screen
      .getAllByTestId('docs-api-tag-group')
      .find((g) => g.getAttribute('data-tag') === 'widgets');
    const endpoints = within(widgetsGroup!).getAllByTestId('docs-api-endpoint');

    // First endpoint: two rows.
    expect(within(endpoints[0]).getByText('page')).toBeVisible();
    expect(within(endpoints[0]).getByText('status')).toBeVisible();
    expect(within(endpoints[0]).getByText('integer<int32>')).toBeVisible();
    expect(within(endpoints[0]).getByText('string (enum)')).toBeVisible();
    expect(within(endpoints[0]).getAllByText('optional')).toHaveLength(1);
    expect(within(endpoints[0]).getAllByText('required')).toHaveLength(1);

    // Second endpoint: no parameters.
    expect(within(endpoints[1]).getAllByText('No parameters')).toHaveLength(1);
  });

  it('flattens the committed spec the same way', () => {
    const operations = collectOpenApiOperations(OPENAPI_SPEC);
    // The committed artifact covers 98 paths; every method is uppercase
    // and every group key resolves through the first tag.
    expect(operations.length).toBeGreaterThan(50);
    for (const op of operations) {
      expect(op.method).toMatch(/^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$/u);
      expect(op.path.startsWith('/')).toBe(true);
    }
    const tags = new Set(operations.flatMap((op) => op.tags ?? []));
    expect(tags.has('agents')).toBe(true);
    expect(tags.has('tasks')).toBe(true);
  });
});
