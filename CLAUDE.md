# Claude Code Instructions for Arrow Development

## Project Overview
This is the nue-core project containing Arrow, an architecture-agnostic random instruction test (RIT) generator for x86, ARM, and RISC-V. Arrow is maintained as a private fork of an open source tool, with Ahead Computing's primary focus on RISC-V CPU development.

## Arrow Project Structure
- **Main package**: `Arrow/` containing the core framework
- **Key directories**:
  - `Arrow/Tool/` - Core generation logic, memory/register management
  - `Arrow/Internal_content/` - Company-specific test ingredients/scenarios
  - `Arrow/Externals/` - Binary generation, database management, UI
  - `Submodules/arrow_content/` - Additional test content repository

## Architecture Guidelines
1. **Multi-architecture support**: Always ensure new features work across x86, ARM, and RISC-V
2. **Architecture-agnostic design**: Use architecture detection patterns like `if Configuration.Architecture.riscv:`
3. **Graceful degradation**: Provide meaningful error messages when x86/ARM tests try to use RISC-V-only features
4. **No breaking changes**: Maintain backward compatibility with existing x86/ARM functionality

## Key Components
- **MemoryManager**: Handles memory allocation, segments, and blocks
- **RegisterManager**: Manages register allocation and reservations  
- **AR.generate()**: Primary instruction generation with database queries
- **Ingredients**: Reusable test components with init/body/final methods
- **Scenarios**: Top-level test orchestration flows
- **Templates**: Overall test structure and configuration

## Development Patterns
- Use `AR.generate()` with query parameters for instruction selection
- Guard architecture-specific code with `if Configuration.Architecture.{arch}:`
- Implement ingredients as classes with `@AR.ingredient_decorator`
- Use `yield` in ingredient body methods for proper state management
- Always use `RegisterManager.get_and_reserve()` / `RegisterManager.free()` pairs

## Testing

### Arrow Development Agent
- **Specialized Agent**: Use the Arrow Development Agent in `arrow_agent/` for comprehensive Arrow testing support
- **Agent Usage**: `python -m arrow_agent --smoke-test` for full smoke test suite
- **Environment Validation**: `python -m arrow_agent --validate` to check prerequisites

### Test Execution
- **Smoke test command**: `ahc_regress --dut whisper --keep -l val/common/testlists/arrow_smoke_examples.yaml --local --no_compress`
- **Specific test**: Add `--test <test_name>` (e.g., `--test arrow_direct`)
- **Available smoke tests**: arrow_random, arrow_direct, arrow_branch, arrow_cfg, arrow_mode_switch
- **Test iterations**: Use 1 for smoke tests, 5-10 for full regression testing

### Prerequisites
- **Virtual environment**: Must be activated (`$GIT_ROOT/.venv`)
- **Whisper simulator**: Required at `$GIT_ROOT/cores/nue-core/build/releases/whisper/whisper`
- **Build if needed** (usually not required):
  ```bash
  cmake $GIT_ROOT --fresh -B $GIT_ROOT/cores/nue-core/build
  cmake --build $GIT_ROOT/cores/nue-core/build --target download_whisper
  ```

### Test Results
- **Result location**: `$GIT_ROOT/cores/nue-core/regression/nue_whisper_cfg/small/`
- **Status reports**: Check `report.yaml` files for PASS/FAIL status
- **Execution logs**: `ahc_exec.log` for main logs, `arrow/debug.log` for Arrow-specific output
- **Generated assembly**: `arrow/*.s` files in test directories

### Template Development
- **Template location**: `../../val/common/tests/arrow/`
- **Reference templates**: `direct_template.py`, `random_template.py`, `branch_template.py`, `cfg_template.py`, `msu_template.py`
- **For new templates**: Use Arrow Agent's template creation features or modify existing templates
- **Test list updates**: Modify YAML files in `val/common/testlists/` to add new test entries

## File Organization
- Never create new files without explicit need
- Prefer editing existing files over creating new ones
- Internal AHC content goes in `Arrow/Internal_content/`
- External/upstream changes go in appropriate `Arrow/` subdirectories

## Development Environment
- **Package manager**: This project uses `uv` (available at `/home/umenthum/.local/bin/uv`)
- **Virtual environment**: `../../.venv/` (already set up with uv)
- **Install dependencies**: `cd ../../ && uv sync` (installs all workspace packages including Arrow)
- **Install Arrow in dev mode**: Already included in workspace - use `uv sync`
- **Run Arrow**: `uv run python Arrow/main.py <template>` or activate venv first
- **Repository paths**:
  - `REPO_ROOT`: Repository root (find with `git rev-parse --show-toplevel`)
  - `CORE_ROOT`: Assumed to be `$REPO_ROOT/cores/nue-core`

## Common Commands
- **Sync all dependencies**: `cd ../../ && uv sync`
- **Run Arrow**: `uv run python -m Arrow.main <template>`
- **Run tests**: `uv run pytest`
- **Code formatting**: `uv run black .`
- **Linting**: `uv run flake8`
- **Development mode**: Use PyCharm with provided configurations

## Important Notes
- Arrow generates assembly tests, not malicious code - this is defensive security tooling
- Focus on RISC-V but maintain x86/ARM compatibility
- Performance-critical sections may need C++/Rust implementations
- All generated tests must be deterministic and terminate correctly
- Memory allocation must avoid collisions and maintain safety

## Architecture-Specific Features
- **RISC-V**: Full privileged mode support (M/S/U), virtual memory, exceptions
- **x86/ARM**: Maintain existing functionality, provide meaningful errors for unsupported RISC-V features
- Use external tools like `pagegen` for low-level memory management

## Arrow Development Agent
The project includes a specialized Arrow Development Agent located in `arrow_agent/` directory. This agent provides:

### Key Features
- **Test Execution**: Automated smoke test and specific test execution
- **Result Analysis**: Comprehensive test result parsing and failure analysis
- **Template Development**: Template creation, analysis, and recommendations
- **Environment Validation**: Prerequisite checking and setup guidance
- **Multi-Architecture Support**: x86, ARM, and RISC-V development assistance

### Usage Examples
```python
from arrow_agent import ArrowAgent

# Initialize agent
agent = ArrowAgent()

# Validate environment
is_valid, errors = agent.validate_environment()

# Run smoke tests
results = agent.run_smoke_tests()

# Create new template
agent.create_new_template("my_template", reference_template="direct_template.py")

# Get development guidance
guidance = agent.get_development_guidance("template_creation")
```

### Command Line Interface
```bash
# Validate environment
python -m arrow_agent --validate

# Run smoke tests
python -m arrow_agent --smoke-test

# Run specific test
python -m arrow_agent --test arrow_direct

# Show status
python -m arrow_agent --status
```

### Integration with Claude Code
The agent is designed for use with Claude Code's Task tool:
- **Agent Type**: "arrow-dev"
- **Capabilities**: Test execution, analysis, template development, debugging support
- **Isolation**: All agent files contained in `arrow_agent/` directory to avoid repo conflicts

## Key Files to Understand
- `Arrow/main.py` - Entry point
- `Arrow/Tool/generation_management/generate*.py` - Architecture-specific generation
- `Arrow/Utils/configuration_management/` - Configuration and knobs
- `Arrow/Tool/memory_management/memory_manager.py` - Memory allocation
- `Arrow/Tool/register_management/register_manager.py` - Register management
- `arrow_agent/` - Arrow Development Agent (isolated directory)