# JSON_Path
![CI](https://github.com/realMNohgee/JSON_Path/actions/workflows/ci.yml/badge.svg) ![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg)

Query and transform JSON with path expressions. Like `jq` for people who don't want to learn `jq`. **Zero dependencies** — Python stdlib only.

## Installation

```bash
curl -O https://raw.githubusercontent.com/realMNohgee/JSON_Path/main/json_path.py
chmod +x json_path.py
```

Or clone:

```bash
git clone git@github.com:realMNohgee/JSON_Path.git
```

## Usage

```bash
# Extract values with path expressions
python3 json_path.py get data.json server.host
python3 json_path.py get data.json "users[0].name"
python3 json_path.py get data.json "users[*].name"
python3 json_path.py get data.json "..name"

# Set values at paths
python3 json_path.py set data.json server.host '"newhost.com"'
python3 json_path.py set data.json database.replicas 3 --output modified.json

# List keys
python3 json_path.py keys data.json
python3 json_path.py keys data.json --path server

# Filter arrays
python3 json_path.py filter data.json "age > 30" --path users
python3 json_path.py filter data.json "active == true" --path users

# Count elements
python3 json_path.py count data.json --path users
```

## Subcommands

| Subcommand | Description | Example |
|-----------|-------------|---------|
| `get` | Extract value at path | `json_path get data.json server.host` |
| `set` | Set value at path (creates intermediates) | `json_path set data.json key "value"` |
| `keys` | List keys at path or root | `json_path keys data.json --path users` |
| `filter` | Filter array items by expression | `json_path filter data.json "age > 30" --path users` |
| `count` | Count elements at path | `json_path count data.json --path users` |

## Path Syntax

| Pattern | Description | Example |
|---------|-------------|---------|
| `key` | Dot notation | `server.host` |
| `[N]` | Array index | `users[0].name` |
| `[*]` | Wildcard (all array items) | `users[*].name` |
| `..key` | Recursive search (any depth) | `..version` |

## Filter Operators

`==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`

```bash
json_path filter data.json "age > 30" --path users
json_path filter data.json "name contains Ali" --path users
json_path filter data.json "active == true" --path users
```

All subcommands support `--format json` for machine-readable output.

## Multi-Domain Use

| Domain | Usage |
|--------|-------|
| DevOps | Extract config values, modify JSON configs |
| Development | Query API responses, test JSON output |
| Data Science | Explore nested JSON datasets, count records |
| System Admin | Parse log files in JSON format |
| QA/Testing | Verify JSON structure, filter test data |
| Automation | Script JSON transformations in shell pipelines |

Built for the [Hermtica Marketplace](https://hermtica.com).
