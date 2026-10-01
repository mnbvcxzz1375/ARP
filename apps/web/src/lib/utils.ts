import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Short disambiguator for same-named users.
 *
 * Usernames are non-unique display labels (backend migration 0030); the
 * UUID user_id is the canonical identifier. Where identity matters
 * (admin tables, member lists), render `username · <shortId>` so two
 * users with the same name stay distinguishable.
 */
export function shortUserId(user_id: string | undefined | null): string {
  if (!user_id) return '';
  return user_id.replace(/-/g, '').slice(0, 8);
}
