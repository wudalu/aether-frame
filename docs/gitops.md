# Aether Frame Git Workflow Guide

## Overview

This document defines the Git branch management strategy for the Aether Frame project, optimized for small team collaboration (2-3 developers), pursuing a simple and efficient workflow.

## Branch Strategy: Simplified GitHub Flow

We adopt a simplified version of **GitHub Flow**, suitable for rapid small team development.

### Core Principles

1. **Keep It Simple** - Minimize branch complexity
2. **Fast Iteration** - Support frequent commits and merges  
3. **Direct Collaboration** - Reduce unnecessary processes

## Branch Structure

### Main Branch

- **`main`** - Main branch containing stable code
  - Can push directly (small team trust mode)
  - Important features merged via Pull Request

### Feature Branches (Optional)

- **`feature/feature-name`** - Used for complex feature development
  - Only for larger feature development
  - Merge to main and delete after completion

## Workflow

### Daily Development (Recommended)

```bash
# Develop directly on main branch
git checkout main
git pull origin main

# Develop and commit
git add .
git commit -m "feat: add new feature"
git push origin main
```

### Complex Feature Development

```bash
# Create feature branch
git checkout -b feature/complex-feature

# After development completion
git checkout main
git pull origin main
git merge feature/complex-feature
git branch -d feature/complex-feature
git push origin main
```

## Commit Standards

Use simplified commit message format:

```
type: description

Types:
- feat: new feature
- fix: bug fix
- docs: documentation
- refactor: code refactoring
- test: testing
```

**Examples:**
```bash
git commit -m "feat: add user login"
git commit -m "fix: resolve data export bug"
git commit -m "docs: update README"
```

## Collaboration Guidelines

### Code Synchronization

- Start each day with: `git pull origin main`
- Ensure tests pass before committing: `python dev.py test`
- Communicate promptly when conflicts arise

### Important Changes Process

For important features or changes that might affect others:

1. Create Pull Request
2. Notify team members
3. Simple code review
4. Merge to main

### Emergency Fixes

```bash
# Fix directly on main
git checkout main
git pull origin main

# Fix and push
git add .
git commit -m "hotfix: critical bug fix"
git push origin main

# Notify team
```

## Version Management

### Simple Tagging

```bash
# Tag when releasing
git tag v1.0.0
git push origin v1.0.0
```

### Version Number Rules

- v1.0.0 - Major version
- v1.1.0 - New feature version  
- v1.1.1 - Bug fix version

## Best Practices

### Commit Frequency
- Commit when small features are complete
- At least one commit per day
- Avoid large batch commits

### Communication and Collaboration
- Communicate important changes in advance
- Discuss problems promptly
- Sync progress regularly

### Code Quality
- Run before committing: `python dev.py lint`
- Ensure tests pass: `python dev.py test`
- Keep code clean

## Tool Usage

### Development Environment
```bash
# Initialize environment
python dev.py venv-init
python dev.py setup-dev
```

### Daily Commands
```bash
# Check code
python dev.py lint

# Run tests  
python dev.py test

# Format code
python dev.py format
```

## Conflict Resolution

### Merge Conflicts
1. Communicate to confirm modification intent
2. Manually resolve conflicts
3. Test to ensure no issues
4. Commit merge results

### Emergency Situations
- Revert immediately if problems occur: `git revert <commit>`
- Notify team members
- Collaborate to resolve issues

## Summary

This simplified workflow is suitable for 2-3 person small teams:

- **Flexibility** - Choose processes based on actual situations
- **Efficiency** - Reduce unnecessary steps
- **Collaboration** - Value communication over process
- **Quality** - Maintain code standards

Team members should flexibly apply these guidelines based on specific situations, with the goal of improving development efficiency.