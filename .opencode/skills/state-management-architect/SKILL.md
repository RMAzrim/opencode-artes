---
name: state-management-architect
description: Implement clean application state management patterns (Zustand, Redux Toolkit, Pinia) with atomic state updates.
metadata:
  source: skills/state-management-architect/state-management-architect.md
---

# State Management Architect

## Prerequisites & Dependencies
- React 16.8+ or Vue 3 project
- Mandatory library: `npm i zustand` (or `npm i @reduxjs/toolkit` / `npm i pinia` for Vue)
- TypeScript recommended for type-safe reducers/actions

## Execution Steps
1. Choose the state library matching the framework (Zustand for React lightweight, Redux Toolkit for enterprise, Pinia for Vue)
2. Define a store/slice with immutable state updates and explicit reducers/actions
3. Wire the store into root component (`provideStore`, `useStore`, or `usePinia`)
4. Implement atomic state updates: dispatch actions that return new state objects, avoid direct mutations
5. Selector patterns: compute derived state using `createSelector` (RTS) or Zustand's `useStoreState`
6. Persist critical state to `localStorage`/`sessionStorage` or backend using library built-ins
7. Test state transitions with `redux-mock-store` or Vue Test Utils, ensure no side effects leak

```typescript
// Zustand store example with atomic updates
import create from 'zustand';

interface CounterState {
  count: number;
  increment: (by: number) => void;
  decrement: (by: number) => void;
}

export const useCounter = create<CounterState>((set) => ({
  count: 0,
  increment: (by = 1) => set((state) => ({ count: state.count + by })),
  decrement: (by = 1) => set((state) => ({ count: state.count - by })),
}));
```
