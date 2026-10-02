import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ContentPreview from '../ContentPreview';
import { classifyContentPreview } from '../../lib/contentView';

/**
 * Mirrors the backend read-side degradation view
 * (apps/api/app/services/message_content_view.build_content_view):
 * the dashboard serializes the classified view to a masked JSON string,
 * so these are the exact shapes a preview can carry.
 */
const encryptedPreview = JSON.stringify({
  encrypted: true,
  security: {
    mode: 'e2ee',
    encryption: 'X25519+HKDF-SHA256+AES-256-GCM',
    key_id: 'key-abc123',
    nonce: 'bm9uY2U=',
  },
  encrypted_payload: 'Y2lwaGVydGV4dA==',
  aad: { alg: 'Ed25519' },
});

const parseErrorPreview = JSON.stringify({
  encrypted: false,
  encrypted_parse_error: true,
  security: { mode: 'e2ee' },
  reason: 'security.nonce is missing or not valid base64',
});

describe('classifyContentPreview', () => {
  it('classifies a null preview as plain', () => {
    expect(classifyContentPreview(null)).toEqual({ kind: 'plain' });
    expect(classifyContentPreview(undefined)).toEqual({ kind: 'plain' });
    expect(classifyContentPreview('')).toEqual({ kind: 'plain' });
  });

  it('classifies a well-formed ciphertext view as encrypted with its key id', () => {
    expect(classifyContentPreview(encryptedPreview)).toEqual({
      kind: 'encrypted',
      keyId: 'key-abc123',
    });
  });

  it('classifies a malformed ciphertext view as a parse error with reason', () => {
    expect(classifyContentPreview(parseErrorPreview)).toEqual({
      kind: 'parse_error',
      reason: 'security.nonce is missing or not valid base64',
    });
  });

  it('degrades to plain for non-JSON or non-object previews', () => {
    expect(classifyContentPreview('not json')).toEqual({ kind: 'plain' });
    expect(classifyContentPreview('[1, 2, 3]')).toEqual({ kind: 'plain' });
    expect(classifyContentPreview('"just a string"')).toEqual({ kind: 'plain' });
  });

  it('degrades to plain for plaintext payloads without marker flags', () => {
    expect(classifyContentPreview('{"action": "test"}')).toEqual({ kind: 'plain' });
    // relay_visible marker blocks stay plaintext-shaped (no flags).
    expect(
      classifyContentPreview(
        JSON.stringify({
          security: { mode: 'relay_visible', encryption: 'none' },
          payload: { action: 'test' },
        }),
      ),
    ).toEqual({ kind: 'plain' });
  });
});

describe('ContentPreview', () => {
  it('renders the placeholder dash for an absent preview', () => {
    render(<ContentPreview preview={null} />);
    expect(screen.getByText('-')).toBeInTheDocument();
  });

  it('renders a plaintext preview as raw text without a chip', () => {
    render(<ContentPreview preview={'{"action": "test"}'} />);
    expect(screen.getByText('{"action": "test"}').tagName).toBe('PRE');
    expect(screen.queryByText('E2EE Ciphertext')).not.toBeInTheDocument();
    expect(screen.queryByText('Ciphertext Parse Error')).not.toBeInTheDocument();
  });

  it('badges an encrypted preview and shows the key id, keeping the raw ciphertext as text', () => {
    render(<ContentPreview preview={encryptedPreview} />);
    expect(screen.getByText('E2EE Ciphertext')).toBeInTheDocument();
    expect(screen.getByText(/Key ID: key-abc123/)).toBeInTheDocument();
    // The ciphertext itself is never parsed away — the raw view is shown.
    expect(screen.getByText(encryptedPreview)).toBeInTheDocument();
  });

  it('badges a parse-error preview with its backend reason', () => {
    render(<ContentPreview preview={parseErrorPreview} />);
    expect(screen.getByText('Ciphertext Parse Error')).toBeInTheDocument();
    expect(
      screen.getByText('security.nonce is missing or not valid base64'),
    ).toBeInTheDocument();
    expect(screen.getByText(parseErrorPreview).tagName).toBe('PRE');
  });
});
