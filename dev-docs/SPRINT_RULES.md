# Sprint & Task Rules

## Sprint Sizing

- A sprint should contain **4-12 tasks**
- Each task should take **30 minutes to half a day**
- Maximum **3 P0 (critical) tasks per sprint**

## Task Rules

### Every task MUST have:
1. Clear context — WHY this task exists
2. Specific requirements — numbered, testable
3. Acceptance criteria — checkboxes defining "done"
4. Dependencies listed
5. Effort estimate

### Every task MUST NOT:
1. Bundle unrelated work
2. Be vague ("improve the UI" is not a task)
3. Assume context the AI won't have
4. Include scope creep ("and any other improvements")

## Execution

### Starting a task
1. Read the task spec completely
2. Read .clinerules, LEARNINGS.md, and the sprint plan
3. Use plan mode to propose approach
4. Get approval, then execute

### Discovering new work during a task
- Bug in current task scope → fix it now
- Bug in a different area → write a task doc, don't fix inline
- "Nice to have" → add to backlog
- Architectural issue → stop, discuss with human

### Finishing a task
1. Run all tests
2. Update task status to DONE
3. Provide confidence score (8/10 minimum to ship)
4. Update LEARNINGS.md if anything discovered
5. Commit with clear message referencing task ID
6. Move to next task in a **fresh conversation**

## The Golden Rule

**Better to finish 6 well-tested, documented tasks than to half-finish 12.**
