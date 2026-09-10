---
id: design-pattern-implementer
file_path: skills/design-pattern-implementer.md
name: Design Pattern Implementer
category: software-architecture
tags: [object-oriented, design-patterns, refactoring, architecture]
author: opencode-core
version: 1.0.0
description: Refactor code to apply object-oriented design patterns (Factory, Strategy, Observer, Decorator, Adapter) cleanly.
---

# Design Pattern Implementer

## Prerequisites & Dependencies
- Node.js 18+ or Python 3.10+ with refactoring tools enabled
- IDE support (VS Code, IntelliJ) for pattern detection
- Working knowledge of OOP principles and UML diagrams

## Execution Steps
1. Survey the codebase and identify areas suffering from tight coupling or rigid structure
2. Select the appropriate pattern (Factory for object creation, Strategy for interchangeable algorithms, Observer for event handling, Decorator for adding responsibilities, Adapter for interface compatibility)
3. Apply the pattern by extracting interfaces, creating wrapper classes, or restructuring method calls, preserving external API contracts
4. Run existing tests to verify behavioral parity and ensure no regressions
5. Document the pattern choice and rationale in the project's architecture guide

```typescript
// Factory pattern example in TypeScript
interface Product {
  id: string;
  name: string;
  price: number;
}

class ConcreteProductA implements Product {
  id = 'a'; name = 'Alpha'; price = 10;
}
class ConcreteProductB implements Product {
  id = 'b'; name = 'Beta'; price = 20;
}

class Factory {
  static create(type: string): Product {
    switch (type) {
      case 'a': return new ConcreteProductA();
      case 'b': return new ConcreteProductB();
      default: throw new Error('Unknown product type');
    }
  }
}

const p = Factory.create('a');
console.log(p); // { id: 'a', name: 'Alpha', price: 10 }
```