# terraforder

Sorts top-level Terraform blocks alphabetically, grouped by block type, so files have a predictable layout and smaller diffs.

Before:

```hcl
output "id" { value = aws_instance.web.id }
resource "aws_s3_bucket" "logs" { bucket = "logs" }
variable "region" {}
resource "aws_instance" "web" { ami = "ami-123" }
```

After `terraforder --write main.tf`:

```hcl
variable "region" {}

resource "aws_instance" "web" { ami = "ami-123" }

resource "aws_s3_bucket" "logs" { bucket = "logs" }

output "id" { value = aws_instance.web.id }
```

## Install

Requires Python 3.11+. No third-party dependencies.

```bash
pip install .
```

## Usage

```bash
terraforder main.tf                  # print the sorted file to stdout
terraforder --write ./terraform      # sort every *.tf / *.tfvars in place (recursive)
terraforder --write --backup main.tf # keep the original as main.tf.bak
terraforder --dry-run ./terraform    # print a diff; exit 1 if anything is unsorted
terraforder --check ./terraform      # alias of --dry-run, for CI
terraforder -v --write .             # also list each file's resulting block order
```

Exit codes: `0` success, `1` files need sorting (`--dry-run`), `2` parse/config errors. Files that fail to parse are reported with `file:line:col` and left untouched.

## Sorting rules

- Blocks are grouped in this order: `terraform`, `provider`, `variable`, `locals`, `data`, `resource`, `module`, `moved`, `import`, `removed`, `check`, `output`. Unknown block types come last, alphabetically by type.
- Within a group, blocks are sorted by their labels, case-insensitively (`resource "aws_instance" "web"` sorts by type, then name). Blocks with identical labels, such as aliased `provider "aws"` blocks or multiple `locals`, keep their original relative order.
- Top-level attributes (`.tfvars` files) are sorted by name and come before any blocks.
- Only top-level order changes. Block bodies are kept byte-for-byte, as are line endings (LF/CRLF) and a UTF-8 BOM.
- Blocks are separated by one blank line; consecutive single-line attributes stay together.

### Comments

- Comments directly above a block (no blank line between) move with that block.
- A comment at the top of the file followed by a blank line is treated as a file header and stays at the top.
- Other standalone comments move with the next block. Comments after the last block stay at the end.

## Configuration

Put a `.terraforder.toml` in the directory you run from, or pass `--config FILE`:

```toml
order = ["terraform", "provider", "variable", "locals", "data", "resource", "module", "output"]
```

## pre-commit

```yaml
- repo: <this repository>
  rev: <tag>
  hooks:
    - id: terraforder
```

## Development

```bash
python -m unittest discover -s tests
```
