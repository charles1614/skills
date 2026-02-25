# Codebase Scanning Commands

Execute ALL discovery commands before writing documentation.

## Phase 0: Quick Structure Overview

```bash
echo "=== QUICK STRUCTURE OVERVIEW ==="
# Use tree if available, fallback to find
if command -v tree &>/dev/null; then
    tree -L 3 -I 'node_modules|.git|vendor|target|build|dist|__pycache__|.venv|.tox'
else
    find . -maxdepth 3 -type d | grep -v 'node_modules\|\.git\|vendor\|target\|build\|dist' | head -60
fi
```

## Phase 1: Complete Codebase Enumeration

```bash
echo "=== COMPLETE CODEBASE ENUMERATION ==="
echo "Total source files by type:"
find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" -o -name "*.go" -o -name "*.rs" -o -name "*.java" -o -name "*.c" -o -name "*.cpp" -o -name "*.h" -o -name "*.hpp" -o -name "*.cs" -o -name "*.rb" -o -name "*.php" -o -name "*.swift" -o -name "*.kt" -o -name "*.dart" -o -name "*.scala" \) | grep -v "node_modules\|\.git\|vendor\|target\|_build\|dist\|build" | wc -l

echo "Lines of code:"
find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" -o -name "*.go" -o -name "*.rs" -o -name "*.java" -o -name "*.c" -o -name "*.cpp" -o -name "*.cs" -o -name "*.rb" -o -name "*.php" \) | grep -v "node_modules\|\.git\|vendor\|target\|_build\|dist\|build" | head -5000 | xargs wc -l 2>/dev/null | tail -1

echo "Language distribution:"
echo "Python: $(find . -name "*.py" | grep -v "node_modules\|\.git\|vendor\|target\|test" | wc -l)"
echo "JavaScript/TypeScript: $(find . -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" | grep -v "node_modules\|\.git\|vendor\|test" | wc -l)"
echo "Go: $(find . -name "*.go" | grep -v "vendor\|\.git\|test" | wc -l)"
echo "Rust: $(find . -name "*.rs" | grep -v "target\|\.git\|test" | wc -l)"
echo "Java: $(find . -name "*.java" | grep -v "build\|\.git\|test" | wc -l)"
echo "C/C++: $(find . -name "*.c" -o -name "*.cpp" -o -name "*.h" -o -name "*.hpp" | grep -v "build\|\.git\|test" | wc -l)"
echo "C#: $(find . -name "*.cs" | grep -v "bin\|obj\|\.git\|test" | wc -l)"
echo "Ruby: $(find . -name "*.rb" | grep -v "vendor\|\.git\|test\|spec" | wc -l)"
echo "PHP: $(find . -name "*.php" | grep -v "vendor\|\.git\|test" | wc -l)"
echo "Swift: $(find . -name "*.swift" | grep -v "\.build\|\.git\|test" | wc -l)"
echo "Kotlin: $(find . -name "*.kt" | grep -v "build\|\.git\|test" | wc -l)"
echo "Dart: $(find . -name "*.dart" | grep -v "build\|\.git\|test\|\.dart_tool" | wc -l)"
echo "Scala: $(find . -name "*.scala" | grep -v "target\|\.git\|test" | wc -l)"
```

## Phase 2: Dependency Analysis

```bash
echo "=== DEPENDENCY ANALYSIS ==="
echo "Package manifests found:"
find . -maxdepth 3 -type f \( \
    -name "package.json" -o -name "package-lock.json" -o -name "yarn.lock" \
    -o -name "requirements.txt" -o -name "Pipfile" -o -name "pyproject.toml" -o -name "setup.py" -o -name "setup.cfg" \
    -o -name "Cargo.toml" -o -name "Cargo.lock" \
    -o -name "go.mod" -o -name "go.sum" \
    -o -name "pom.xml" -o -name "build.gradle" -o -name "build.gradle.kts" \
    -o -name "Gemfile" -o -name "composer.json" \
    -o -name "*.csproj" -o -name "*.sln" \
    -o -name "pubspec.yaml" -o -name "build.sbt" \
\) | grep -v "node_modules\|\.git\|vendor\|target\|build\|dist"

echo "Key dependencies (top-level):"
# Node.js
[ -f package.json ] && echo "--- package.json dependencies ---" && cat package.json | grep -A 50 '"dependencies"' | head -30
# Python
[ -f requirements.txt ] && echo "--- requirements.txt ---" && head -30 requirements.txt
[ -f pyproject.toml ] && echo "--- pyproject.toml dependencies ---" && grep -A 20 '\[project\]' pyproject.toml | head -25
# Go
[ -f go.mod ] && echo "--- go.mod ---" && head -30 go.mod
# Rust
[ -f Cargo.toml ] && echo "--- Cargo.toml dependencies ---" && grep -A 30 '\[dependencies\]' Cargo.toml | head -35
# Ruby
[ -f Gemfile ] && echo "--- Gemfile ---" && head -30 Gemfile
# PHP
[ -f composer.json ] && echo "--- composer.json ---" && cat composer.json | grep -A 30 '"require"' | head -30
```

## Phase 3: Deep Architecture Scanning

```bash
echo "=== DEEP ARCHITECTURE SCANNING ==="
echo "All entry points and main files:"
find . -type f \( -name "main.*" -o -name "__main__.py" -o -name "index.*" -o -name "app.*" -o -name "server.*" -o -name "run.*" \) | grep -v "node_modules\|\.git\|test\|dist\|build"

echo "All core modules:"
find . -type f \( -name "*manager*" -o -name "*controller*" -o -name "*handler*" -o -name "*service*" -o -name "*core*" -o -name "*engine*" -o -name "*worker*" \) | grep -v "node_modules\|\.git\|test\|dist\|build"

echo "All configuration files:"
find . -type f \( -name "*config*" -o -name "*settings*" -o -name "*options*" -o -name "*env*" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" \) | grep -v "node_modules\|\.git\|test\|dist\|build"
```

## Phase 4: API and Interface Discovery

```bash
echo "=== API AND INTERFACE DISCOVERY ==="
echo "All API definitions:"
find . -type f \( -name "*api*" -o -name "*openapi*" -o -name "*swagger*" -o -name "*proto*" -o -name "*schema*" \) | grep -v "node_modules\|\.git\|test\|dist\|build"

echo "All HTTP/server components:"
find . -type f \( -name "*server*" -o -name "*http*" -o -name "*route*" -o -name "*endpoint*" -o -name "*middleware*" \) | grep -v "node_modules\|\.git\|test\|dist\|build"

echo "CLI interfaces:"
find . -type f \( -name "*cli*" -o -name "*command*" -o -name "*cmd*" \) | grep -v "node_modules\|\.git\|test\|dist\|build"
```

## Phase 5: Data and Infrastructure Mapping

```bash
echo "=== DATA AND INFRASTRUCTURE MAPPING ==="
echo "Database/data layer:"
find . -type f \( -name "*model*" -o -name "*schema*" -o -name "*repository*" -o -name "*dao*" -o -name "*migration*" -o -name "*seed*" -o -name "*entity*" \) | grep -v "node_modules\|\.git\|test\|dist\|build"

echo "Testing infrastructure:"
find . -type f \( -name "*test*" -o -name "*spec*" \) | grep -v "node_modules\|\.git"

echo "Build and deployment:"
find . -type f \( -name "webpack*" -o -name "vite*" -o -name "rollup*" -o -name "*dockerfile*" -o -name "docker-compose*" \) | grep -v "node_modules\|\.git" | head -20
find . -type d \( -name ".github" -o -name ".gitlab-ci*" \) | head -10
```

## Pattern Detection

```bash
echo "=== ARCHITECTURE PATTERN DETECTION ==="
echo "Design patterns in code:"
grep -r -i "singleton\|factory\|observer\|decorator\|strategy\|proxy\|adapter\|command\|facade" --include="*.py" --include="*.js" --include="*.ts" --include="*.go" --include="*.java" --include="*.cs" --include="*.rb" | head -30

echo "Concurrency patterns:"
grep -r -i "async\|await\|thread\|process\|goroutine\|mutex\|lock\|semaphore\|channel\|coroutine" --include="*.py" --include="*.js" --include="*.ts" --include="*.go" --include="*.rs" | head -30

echo "Communication patterns:"
grep -r -i "grpc\|zmq\|redis\|rabbitmq\|kafka\|websocket\|http\|rest\|graphql\|message.*queue" --include="*.py" --include="*.js" --include="*.ts" --include="*.go" | head -30
```

## Feature and Capability Discovery

```bash
echo "=== FEATURE AND CAPABILITY DISCOVERY ==="
echo "Database integrations:"
grep -r -i "database\|db\|sql\|nosql\|mysql\|postgres\|mongodb\|sqlite\|oracle" --include="*.py" --include="*.js" --include="*.ts" --include="*.go" | head -30

echo "Caching mechanisms:"
grep -r -i "cache\|lru\|ttl\|expire\|memory.*cache\|redis.*cache" --include="*.py" --include="*.js" --include="*.ts" | head -20

echo "Error handling patterns:"
grep -r -i "try.*catch\|except\|error\|exception\|fail\|retry\|circuit.*breaker\|fallback" --include="*.py" --include="*.js" --include="*.ts" --include="*.java" | head -30

echo "Security/Authentication:"
grep -r -i "auth\|jwt\|oauth\|token\|password\|hash\|encrypt\|sign\|certificate" --include="*.py" --include="*.js" --include="*.ts" | head -20
```

## Component Structure Analysis

```bash
echo "=== COMPONENT STRUCTURE ANALYSIS ==="
echo "Classes and structures:"
grep -r "^\s*class\|^\s*struct\|^\s*interface\|^\s*type.*struct" --include="*.py" --include="*.js" --include="*.ts" --include="*.go" --include="*.rs" --include="*.java" --include="*.cs" --include="*.kt" | head -50

echo "Functions and methods (by language):"
echo "-- Python --"
grep -rn "^\s*\(def\|class\|async def\) " --include="*.py" | grep -v "node_modules\|\.git\|test" | head -20
echo "-- JavaScript/TypeScript --"
grep -rn "^\s*\(export\s\+\)\?\(async\s\+\)\?\(function\|class\) " --include="*.js" --include="*.ts" --include="*.tsx" | grep -v "node_modules\|\.git\|test\|dist" | head -20
echo "-- Go --"
grep -rn "^func " --include="*.go" | grep -v "vendor\|\.git\|test" | head -20
echo "-- Java/Kotlin --"
grep -rn "^\s*\(public\|private\|protected\)\s\+.*\s\+\w\+(.*)" --include="*.java" --include="*.kt" | grep -v "build\|\.git\|test" | head -20

echo "API routes and endpoints:"
grep -r -i "endpoint\|route\|@.*route\|@.*api\|app\.\(get\|post\|put\|delete\)\|router\." --include="*.py" --include="*.js" --include="*.ts" | head -30
```

## Quality and Maintenance Indicators

```bash
echo "=== QUALITY AND MAINTENANCE ==="
echo "Testing patterns:"
grep -r -i "describe\|it\(|test\|assert\|expect\|mock\|spec" --include="*.py" --include="*.js" --include="*.ts" | head -20

echo "Monitoring and observability:"
grep -r -i "logger\.\|logging\.\|metrics\.\|prometheus\|opentelemetry\|datadog\|newrelic\|sentry\|telemetry" --include="*.py" --include="*.js" --include="*.ts" --include="*.go" | head -20

echo "Technical debt indicators:"
grep -r "TODO\|FIXME\|HACK\|NOTE\|XXX\|BUG\|DEPRECATED" --include="*.py" --include="*.js" --include="*.ts" --include="*.go" | head -20
```

## Image and Visual Assets Discovery

```bash
echo "=== IMAGE AND VISUAL ASSETS DISCOVERY ==="

# Find all image files
find . -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.gif" -o -iname "*.svg" -o -iname "*.webp" \) | grep -v "node_modules\|\.git\|vendor\|target\|build\|dist" | head -50

# Find images in documentation directories
find . -type f \( -path "*/docs/*" -o -path "*/documentation/*" -o -path "*/images/*" -o -path "*/assets/*" -o -path "*/img/*" \) | grep -E "\.(png|jpg|jpeg|gif|svg|webp)$" | head -30

# Find architecture diagrams and design assets
find . -type f \( -iname "*architecture*" -o -iname "*diagram*" -o -iname "*design*" -o -iname "*flow*" -o -iname "*chart*" \) | grep -E "\.(png|jpg|jpeg|svg|webp)$" | head -20
```

## Project Evolution Discovery

```bash
echo "=== PROJECT EVOLUTION ==="
# Check if this is a git repo first
if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    # Version history
    git tag -l | tail -10

    # Recent changes
    git log --oneline --graph --decorate -20

    # Top contributors
    echo "Top contributors:"
    git shortlog -sn --no-merges | head -10

    # Most frequently changed files (core vs peripheral)
    echo "Most frequently changed files (last 6 months):"
    git log --since="6 months ago" --name-only --format="" | sort | uniq -c | sort -rn | head -20

    # Current commit hash for documentation metadata
    echo "Current commit: $(git rev-parse --short HEAD)"
else
    echo "Not a git repository - skipping git-based analysis"
fi

# Changelog/roadmap files
find . -maxdepth 2 -type f \( -name "CHANGELOG*" -o -name "HISTORY*" -o -name "ROADMAP*" -o -name "TODO*" \) | head -10
```

## Maximum Coverage Requirements

**Mandatory thresholds** - Documentation must cover:

| Codebase Size | Minimum File Analysis |
|---------------|----------------------|
| < 1000 files | Analyze ALL files |
| 1000-5000 files | At least 2000 files (40%+) |
| 5000+ files | At least 3000 files (60%+) |

**Minimum code line analysis:**
- Must analyze at least 10,000 lines of code
- For large codebases: at least 50,000 lines

**Coverage requirements:**
- ALL top-level directories documented
- ALL main application entry points identified
- ALL configuration files and settings
- ALL external integrations and dependencies
- ALL REST endpoints found
- ALL database schemas/models found
- ALL authentication mechanisms found

## Verification Checklist

Before generating final documentation:

- [ ] Codebase Statistics: Total files, languages, lines of code documented
- [ ] Architecture Coverage: All major patterns, components, and relationships identified
- [ ] API Coverage: All endpoints, schemas, and interfaces documented
- [ ] Configuration Coverage: All config files and settings analyzed
- [ ] Dependency Mapping: All external services and libraries documented
- [ ] Quality Analysis: Testing patterns, monitoring, and technical debt noted
- [ ] Image Integration: All relevant project images discovered
- [ ] Source Citation: Every major claim backed by specific file paths and line numbers
