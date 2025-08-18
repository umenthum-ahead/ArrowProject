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
- **Primary test command**: `ahc_regress -l ../../val/common/testlists/riscv_dv_whisper_doa.yaml --dut whisper --test arrow_direct --keep`
- **Build prerequisites** (usually not needed): 
  ```bash
  cmake $REPO_ROOT -B $CORE_ROOT/build
  cmake --build $CORE_ROOT/build --target download_whisper
  ```
  Skip if `$CORE_ROOT/build/releases/whisper/whisper` already exists (usually the case)
- **For new test templates**: Modify the test list YAML file and use `--test <new_entry_name>` to specify the new test entry
- Test templates are in `../../val/common/tests/arrow/`

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

## Key Files to Understand
- `Arrow/main.py` - Entry point
- `Arrow/Tool/generation_management/generate*.py` - Architecture-specific generation
- `Arrow/Utils/configuration_management/` - Configuration and knobs
- `Arrow/Tool/memory_management/memory_manager.py` - Memory allocation
- `Arrow/Tool/register_management/register_manager.py` - Register management