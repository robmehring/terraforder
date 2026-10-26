# Terraforder: Terraform Code Alphabetizer

## Problem Statement

Terraform configuration files often contain resources, variables, outputs, and other blocks that are defined in an inconsistent order. This inconsistency can lead to:
- Difficulty reviewing diffs when the order changes between versions
- Increased merge conflicts when different authors add resources in different places
- Reduced readability when scanning code for specific resources
- Unpredictable code layout that makes it harder to maintain large configurations

## Solution Overview

**Terraforder** is a tool that automatically organizes Terraform code into a consistent, alphabetical order. It will parse `.tf` files, group blocks by type (resource, variable, output, data, locals, etc.), and sort them alphabetically within each group to ensure deterministic, readable Terraform configurations.

## Scope

### In Scope
- Parse HCL/Terraform syntax
- Sort blocks alphabetically within categories:
  - Resources
  - Variables
  - Outputs
  - Data sources
  - Locals
  - Terraform blocks
  - Provider blocks
- Preserve comments and formatting as much as possible
- Process single files or entire directories
- Output formatted, ordered code
- Optional in-place file modification or dry-run mode

### Out of Scope
- Style formatting (tabs vs spaces, line lengths)
- Resource-specific validation
- Module dependency analysis
- Terraform plan/apply operations

## Implementation Approach

### Architecture
1. **Parser**: Use an HCL parser library (e.g., HCL2 in Go or Python's `hcl2` package) to extract block structure
2. **Sorter**: Group blocks by type, then sort alphabetically by block name
3. **Formatter**: Reconstruct the Terraform code with sorted blocks while preserving comments and structure
4. **CLI**: Command-line interface for file/directory processing

### Technology Options

**Option A: Go**
- Leverage Terraform's own HCL parser (`hashicorp/hcl`)
- Compile to single binary
- Fast performance for large codebases
- Better alignment with Terraform ecosystem

**Option B: Python**
- Faster development with `hcl2` library
- Easier cross-platform support
- Good for rapid prototyping

**Recommendation**: Go (Option A) for production-grade tool

### Key Features
- **Dry-run mode**: Show what would be changed without modifying files
- **Recursive processing**: Handle entire directories
- **Backup option**: Create `.bak` files before modifying
- **Verbose output**: Show sorting operations performed
- **Config file support**: Allow customization of sort order per project

## Example Usage

```bash
# Sort single file
terraforder main.tf

# Sort entire directory
terraforder ./terraform

# Dry-run
terraforder --dry-run ./terraform

# In-place modification
terraforder --write ./terraform

# Custom sort order via config
terraforder --config .terraforder.yaml ./terraform
```

## Benefits

1. **Consistency**: Deterministic code order across teams
2. **Readability**: Alphabetical order makes code easier to navigate
3. **Reduced merge conflicts**: Consistent ordering reduces diff conflicts
4. **Maintainability**: Easier to locate resources when reviewing code
5. **CI/CD integration**: Can be run as pre-commit hook or in pipeline
6. **Reversible**: Works alongside standard Terraform formatting tools

## Technical Considerations

### Challenges
- Preserving inline and block comments
- Handling multi-line strings correctly
- Managing complex nested structures
- Supporting various Terraform versions

### Compatibility
- Target Terraform 1.0+
- Support both `.tf` files and `.tfvars` files
- Compatible with providers and modules

## Success Metrics

1. Correctly sorts 100% of valid HCL syntax
2. Preserves all comments without loss
3. Produces output that `terraform fmt` considers valid
4. Processes 1000+ lines of code in < 1 second
5. Zero false positives/syntax errors in output

## Next Steps

1. Create a prototype parser for basic HCL syntax
2. Test on real-world Terraform configurations
3. Build sorting and formatting logic
4. Implement CLI interface
5. Add comprehensive test suite
6. Write documentation and usage guide

---

**Status**: Proposal  
**Last Updated**: 2026-10-26
