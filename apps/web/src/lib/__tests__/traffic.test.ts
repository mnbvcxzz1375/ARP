import { describe, it, expect } from 'vitest';
import { changedRoutes, stableAgentOrder, type TaskTrafficRoute } from '../traffic';
const route = (from: string, to: string, queued = 1): TaskTrafficRoute =>
  ({ from, to, running: 0, queued, awaiting_approval: 0, failed_24h: 0, revision: 'v1' });
describe('traffic display budget', () => {
  it('does not animate initial snapshots or unchanged routes; only the changed pair', () => {
    const before = [route('a','b'), route('a','c')];
    expect(changedRoutes(null, before)).toEqual([]);
    expect(changedRoutes(before, before)).toEqual([]);
    expect(changedRoutes(before, [route('a','b',2), route('a','c')])).toEqual(['a:b']);
  });
  it('bounds simultaneous packets and excludes failure-only and off-focus routes', () => {
    const after = Array.from({length:8}, (_,i)=>route('a',String(i)));
    after.push({...route('z','x',0), failed_24h:3});
    expect(changedRoutes([], after)).toHaveLength(3);
    expect(changedRoutes([], after, '0')).toEqual(['a:0']);
  });
  it('preserves existing island order when new random agent numbers arrive', () => {
    expect(stableAgentOrder(['b','c'], ['a','c','b'])).toEqual(['b','c','a']);
    expect(stableAgentOrder(['b','c'], ['a','c'])).toEqual(['c','a']);
  });
});
