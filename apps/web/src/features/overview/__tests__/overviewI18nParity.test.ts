import { describe, it, expect } from 'vitest';
import en from '../../../i18n/locales/en/overview';
import zh from '../../../i18n/locales/zh/overview';

/**
 * en/zh overview shards must stay key-aligned: the design requires new
 * copy to land in both locales (the pixel face carries no CJK glyphs, so
 * zh keeps the CJK fallback stack — the pair is structural, not
 * optional). Locales are auto-gathered by import.meta.glob in
 * i18n/core.ts, so a missing zh key would render as the English fallback
 * (translate() degrades gracefully); this test fails the build first.
 */
describe('overview locale parity', () => {
  it('defines the same key set in en and zh', () => {
    const enKeys = Object.keys(en).sort();
    const zhKeys = Object.keys(zh).sort();
    expect(zhKeys).toEqual(enKeys);
  });

  it('keeps the legacy 19 keys intact', () => {
    const legacy = [
      'title',
      'error.load',
      'stat.onlineAgents',
      'stat.tasksToday',
      'stat.failedTasks',
      'stat.pendingApprovals',
      'stat.pendingMessages',
      'hero.title',
      'hero.agentA',
      'hero.agentB',
      'summary.failed',
      'summary.idle',
      'summary.nominal',
      'section.recentTasks',
      'section.recentApprovals',
      'table.id',
      'table.status',
      'table.created',
      'table.risk',
    ];
    for (const key of legacy) {
      expect(en).toHaveProperty(key);
      expect(zh).toHaveProperty(key);
    }
  });
});
