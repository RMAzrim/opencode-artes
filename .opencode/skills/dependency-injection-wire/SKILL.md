---
name: Dependency Injection Wiring
description: Decouple code modules using Inversion of Control (IoC) containers and explicit interface abstractions.
metadata:
  source: skills/dependency-injection-wire/dependency-injection-wire.md
---

# Dependency Injection Wiring

## Prerequisites & Dependencies
- TypeScript 5+ (recommended) or Python 3.10+
- Understanding of interfaces and inversion of control principles
- Optional: `npm i inversify` / `pip i dependency-injector` or manual DI container

## Execution Steps
1. Define interfaces for all high-level dependencies (database, email service, external APIs)
2. Create concrete implementations of those interfaces
3. Build a DI container (or use an existing one) that maps interfaces → implementations
4. Request dependencies via constructor injection or property injection, avoid `new` or global singletons in business logic
5. Wire the container at the application bootstrap (e.g., `index.ts`, `main.py`) and verify that swapping implementations (mock vs real) is trivial for testing
6. Document the DI graph and ensure no circular dependencies exist

```typescript
// InversifyJS example: interface → implementation wiring
import { injectable, inject, interfaces } from 'inversify';
import { TYPES } from './types';

@injectable()
class UserService {
  constructor(@inject(TYPES.IUserRepository) private repo: IUserRepository) {}
  async getById(id: string) { return this.repo.find(id); }
}

@injectable()
class UserRepository implements IUserRepository {
  async find(id: string) { /* DB logic */ }
}

const container = new Container();
container.bind<IUserRepository>(TYPES.IUserRepository).to(UserRepository);

// Bootstrap app with resolved dependencies
const service = container.get(UserService);
service.getById('123');
```
