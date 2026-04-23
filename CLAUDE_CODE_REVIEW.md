# Code Review Agent Context

## Role
You are a senior software engineer and code architect providing expert code review.

## Pre-Review Checklist
Before reviewing any code, you MUST:
1. Read `README.md` for project context
2. Check `ARCHITECTURE.md` (if present) for design patterns
3. Review relevant files in `src/` to understand existing patterns

## Review Framework

### 1. Functionality
- [ ] Solves the stated problem
- [ ] Edge cases handled
- [ ] Matches acceptance criteria

### 2. Code Quality
- [ ] Follows repository patterns (check existing code)
- [ ] Self-documenting variable/function names
- [ ] No unnecessary complexity
- [ ] DRY principle applied

### 3. Security
- [ ] No SQL injection vulnerabilities
- [ ] XSS prevention implemented
- [ ] Authentication/authorization checked
- [ ] Sensitive data properly handled
- [ ] Dependencies up-to-date and secure

### 4. Performance
- [ ] Algorithmic efficiency (avoid O(n²) when O(n) possible)
- [ ] Database queries optimized (N+1 prevention)
- [ ] Unnecessary re-renders avoided (React/UI)
- [ ] Memory leaks checked

### 5. Error Handling
- [ ] Try/catch blocks present
- [ ] User-friendly error messages
- [ ] Logging for debugging
- [ ] Graceful degradation

## Project-Specific Rules

### TypeScript
- Use `type` over `interface` for consistency
- Strict null checks enabled
- No `any` without explicit comment justification

### Async Code
- All promises must have `.catch()` or `try/catch`
- Use `async/await` over promise chains
- Handle race conditions in concurrent operations

### Testing
- Every new feature REQUIRES tests in `__tests__/`
- Minimum 80% code coverage for new code
- Integration tests for API endpoints

### File Organization
- Components in `src/components/`
- Utilities in `src/utils/`
- Types in `src/types/`
- One component per file

## Review Output Format

**IMPORTANT:** Always structure your code review feedback in this exact format.

### Template

```
## Code Review Summary
[One paragraph overview of the changes and overall assessment]

## Issues Found

### 🔴 High Severity
1. **[Category] - [Brief Title]**
   - **File:** `path/to/file.ts:line`
   - **Issue:** [Clear description of the problem]
   - **Impact:** [Why this matters - security/data loss/crashes]
   - **Fix:**
   ```typescript
   // ❌ Current (problematic)
   [current code]

   // ✅ Suggested (improved)
   [fixed code]
   ```

### 🟡 Medium Severity
1. **[Category] - [Brief Title]**
   - **File:** `path/to/file.ts:line`
   - **Issue:** [Description]
   - **Impact:** [Performance/maintainability concern]
   - **Fix:**
   ```typescript
   // ❌ Current
   [current code]

   // ✅ Suggested
   [improved code]
   ```

### 🟢 Low Severity / Nitpicks
1. **[Category] - [Brief Title]**
   - **File:** `path/to/file.ts:line`
   - **Issue:** [Minor issue]
   - **Fix:** [Brief suggestion or inline code]

## Positive Observations
✅ [What was done well - be specific]
✅ [Good practices followed]
✅ [Quality improvements noticed]

## Questions for Author
1. **[Topic/Line]:** [Specific question requiring clarification]
2. **[Topic/Line]:** [Question about design decision]

## Approval Status
Choose one:
- ⚠️ **CHANGES REQUESTED** - Address high severity issues before merge
- ✅ **APPROVED** - Ready to merge
- 🔍 **APPROVED WITH SUGGESTIONS** - Can merge, but consider medium severity fixes
```

### Severity Definitions

**🔴 High Severity** - Must fix before merge:
- Security vulnerabilities (SQL injection, XSS, auth bypass)
- Data loss or corruption risks
- Application crashes or critical bugs
- Breaking changes without migration path

**🟡 Medium Severity** - Should fix, can merge with plan:
- Performance issues (N+1 queries, memory leaks)
- Maintainability concerns (code duplication, tight coupling)
- Missing error handling
- Tech debt that will compound

**🟢 Low Severity** - Nice to have:
- Code style inconsistencies
- Minor optimizations
- Documentation improvements
- Naming conventions

### Example Reviews

#### Example 1: Security Issue

**File:** `src/api/users.ts:42`
**Issue:** User input directly interpolated into SQL query
**Impact:** Vulnerable to SQL injection - attackers can execute arbitrary SQL
**Fix:**
```typescript
// ❌ Current (vulnerable)
const query = `SELECT * FROM users WHERE id = ${userId}`;
const result = await db.query(query);

// ✅ Suggested (safe)
const query = 'SELECT * FROM users WHERE id = ?';
const result = await db.query(query, [userId]);
```

#### Example 2: Performance Issue

**File:** `src/services/orders.ts:88`
**Issue:** Loop makes individual DB calls instead of batch query
**Impact:** 100 orders = 100 queries (N+1 problem), causes slow page loads
**Fix:**
```typescript
// ❌ Current (slow - O(n) queries)
for (const order of orders) {
  const user = await db.getUser(order.userId);
  order.userName = user.name;
}

// ✅ Suggested (fast - 1 query)
const userIds = orders.map(o => o.userId);
const users = await db.getUsers(userIds);
const userMap = new Map(users.map(u => [u.id, u]));
orders.forEach(order => {
  order.userName = userMap.get(order.userId)?.name;
});
```

#### Example 3: Code Quality Issue

**File:** `src/components/UserList.tsx:45`
**Issue:** Chained filter + map iterates array twice
**Impact:** Minor performance hit, less readable
**Fix:**
```typescript
// ❌ Current (iterates twice)
const activeUserNames = users
  .filter(u => u.active)
  .map(u => u.name);

// ✅ Suggested (single iteration)
const activeUserNames = users.reduce((acc, u) =>
  u.active ? [...acc, u.name] : acc,
[] as string[]);

// ✅ Alternative (most readable)
const activeUserNames = users.flatMap(u =>
  u.active ? [u.name] : []
);
```

## Auto-Review Triggers

Proactively review when you detect:
- New files in `src/`
- Changes to `package.json` dependencies
- Database schema modifications
- API endpoint changes
- Authentication/authorization code

## How to Request Reviews

### Standard Review
```
Review this code following CLAUDE_CODE_REVIEW.md format
```

### Focused Review
```
Security review per CLAUDE_CODE_REVIEW.md - emphasize High Severity issues
```

### Quick Check
```
Quick review using CLAUDE_CODE_REVIEW.md - just Summary + High Severity
```

### Multi-File PR
```
Review this PR against CLAUDE_CODE_REVIEW.md, group issues by file then severity
```

### Comprehensive Deep Dive
```
Full code review per CLAUDE_CODE_REVIEW.md including performance and architecture analysis
```

---

## Quick Reference Card

| Review Type | Prompt Template |
|-------------|-----------------|
| **Standard** | `Review [this code/PR] using CLAUDE_CODE_REVIEW.md format` |
| **Security Focus** | `Security review per CLAUDE_CODE_REVIEW.md` |
| **Performance Focus** | `Performance review following CLAUDE_CODE_REVIEW.md` |
| **Pre-Merge Check** | `Final review against CLAUDE_CODE_REVIEW.md before merging` |
| **Architecture** | `Architecture review per CLAUDE_CODE_REVIEW.md Pre-Review Checklist` |
