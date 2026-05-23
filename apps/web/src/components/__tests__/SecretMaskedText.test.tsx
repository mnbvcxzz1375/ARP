import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import SecretMaskedText from '../SecretMaskedText';

describe('SecretMaskedText', () => {
  it('masks secrets by default', () => {
    render(<SecretMaskedText text="ak_test1234567890abcdefghij" />);
    expect(screen.getByText('***')).toBeInTheDocument();
  });

  it('shows text without secrets', () => {
    render(<SecretMaskedText text="hello world" />);
    expect(screen.getByText('hello world')).toBeInTheDocument();
  });

  it('toggles visibility on eye click', () => {
    render(<SecretMaskedText text="sk-test1234567890abcdefghij" />);
    const btn = screen.getByRole('button');
    expect(screen.getByText('***')).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.getByText(/sk-test1234567890/)).toBeInTheDocument();
  });

  it('hides again on second toggle', () => {
    render(<SecretMaskedText text="ak_test1234567890abcdefghij" />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(screen.getByText(/ak_test/)).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.getByText('***')).toBeInTheDocument();
  });

  it('handles empty text', () => {
    const { container } = render(<SecretMaskedText text="" />);
    expect(container.innerHTML).toBe('');
  });

  it('masks multiple secret patterns', () => {
    render(<SecretMaskedText text={"api key: sk-longsecretkey1234567890 token: agt_sk_testtoken1234567890abcde"} />);
    const code = screen.getByText((content) => content.includes('***'));
    expect(code).toBeInTheDocument();
    expect(code.textContent).not.toContain('sk-longsecret');
    expect(code.textContent).not.toContain('agt_sk_testtoken');
  });

  it('masks ak_ keys with underscore chars', () => {
    render(<SecretMaskedText text="ak_abc_def_ghi_jkl_mno_pqr_stu" />);
    expect(screen.getByText('***')).toBeInTheDocument();
  });

  it('masks ak_ keys with hyphen chars', () => {
    render(<SecretMaskedText text="ak_abc-def-ghi-jkl-mno-pqr-stu" />);
    expect(screen.getByText('***')).toBeInTheDocument();
  });

  it('masks ak_ keys with mixed urlsafe chars', () => {
    render(<SecretMaskedText text="ak_aB3_def-xyz_123-QWx_9mn" />);
    expect(screen.getByText('***')).toBeInTheDocument();
  });
});
