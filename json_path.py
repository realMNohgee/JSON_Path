#!/usr/bin/env python3
"""JSON_Path — Query and transform JSON with path expressions.
Like jq for people who don't want to learn jq. Zero deps."""

import argparse
import json
import os
import sys
import re


def parse_path(path_str):
    """Parse a path string into a list of segments.
    Supports: dot notation (server.host), bracket notation (users[0].name),
    wildcard (users[*].name), recursive search (..name).
    """
    segments = []
    i = 0
    while i < len(path_str):
        if path_str[i] == ".":
            if i + 1 < len(path_str) and path_str[i + 1] == ".":
                segments.append("..")
                i += 2
            else:
                i += 1  # Skip dot, read key
                if i < len(path_str) and path_str[i] == "[":
                    # dot followed by bracket, e.g., .[0]
                    pass
                else:
                    key, i = _read_key(path_str, i)
                    if key:
                        segments.append(key)
        elif path_str[i] == "[":
            i += 1
            if path_str[i] == "*":
                segments.append("*")
                i += 1
            elif path_str[i] == "'" or path_str[i] == '"':
                quote = path_str[i]
                i += 1
                end = path_str.index(quote, i)
                segments.append(path_str[i:end])
                i = end + 1
            else:
                # Numeric index
                j = i
                while j < len(path_str) and path_str[j].isdigit():
                    j += 1
                idx = int(path_str[i:j])
                segments.append(idx)
                i = j
            if i < len(path_str) and path_str[i] == "]":
                i += 1
        else:
            key, i = _read_key(path_str, i)
            if key:
                segments.append(key)
    return segments


def _read_key(s, i):
    """Read a key name starting at position i. Returns (key, new_position)."""
    j = i
    while j < len(s) and s[j] not in ".[" and not (s[j] == "]" and j > i):
        j += 1
    key = s[i:j]
    return key, j


def resolve_path(data, segments, recursive=False):
    """Resolve path segments against data. Returns list of (value, parent, key)."""
    if not segments:
        return [(data, None, None)]

    results = []
    seg = segments[0]
    rest = segments[1:]

    if seg == "..":
        # Recursive descent: check current dict level, then recurse into all children
        if len(rest) == 1 and isinstance(data, dict) and rest[0] in data:
            results.append((data[rest[0]], data, rest[0]))
        elif len(rest) == 0:
            results.append((data, None, None))

        # Recurse into children with the full ".." segment still in segments
        if isinstance(data, dict):
            for k, v in data.items():
                results.extend(resolve_path(v, segments))
        elif isinstance(data, list):
            for v in data:
                results.extend(resolve_path(v, segments))
        return results

    if isinstance(data, dict):
        if seg == "*":
            for k, v in data.items():
                results.extend(resolve_path(v, rest))
        elif seg in data:
            results.extend(resolve_path(data[seg], rest))
        elif recursive and not rest:
            # Recursive search in dicts
            for k, v in data.items():
                results.extend(resolve_path(v, segments))

    elif isinstance(data, list):
        if seg == "*":
            for v in data:
                results.extend(resolve_path(v, rest))
        elif isinstance(seg, int):
            if seg < len(data):
                results.extend(resolve_path(data[seg], rest))
        elif recursive and not rest:
            for v in data:
                results.extend(resolve_path(v, segments))

    return results


def set_value_at_path(data, segments, value):
    """Set a value at a path, creating intermediate keys/indices as needed."""
    if not segments:
        return value

    seg = segments[0]
    rest = segments[1:]

    if rest:
        # Need to go deeper
        if isinstance(data, dict):
            if seg not in data:
                # Determine if next seg is index or key
                next_seg = rest[0]
                data[seg] = [] if isinstance(next_seg, int) else {}
            data[seg] = set_value_at_path(data[seg], rest, value)
        elif isinstance(data, list):
            if isinstance(seg, int):
                while len(data) <= seg:
                    data.append(None)
                data[seg] = set_value_at_path(data[seg], rest, value)
        else:
            # Can't go deeper in a scalar
            return data
    else:
        if isinstance(data, dict):
            data[seg] = value
        elif isinstance(data, list) and isinstance(seg, int):
            while len(data) <= seg:
                data.append(None)
            data[seg] = value
        else:
            # Replace the whole thing
            return value

    return data


def evaluate_filter(item, expression):
    """Evaluate a filter expression like 'age > 30' or 'name == Alice' against an item."""
    # Parse expression
    ops = [">=", "<=", "!=", "==", ">", "<", "contains"]
    found_op = None
    for op in ops:
        if f" {op} " in expression:
            found_op = op
            break
        # Edge case: op at start or with no spaces
        if op in expression:
            parts = expression.split(op, 1)
            if len(parts) == 2:
                found_op = op
                break

    if not found_op:
        return False

    parts = expression.split(f" {found_op} " if f" {found_op} " in expression else found_op, 1)
    if len(parts) != 2:
        return False

    field = parts[0].strip()
    raw_value = parts[1].strip()

    # Get the field value from item
    if isinstance(item, dict):
        if field not in item:
            return False
        actual = item[field]
    else:
        return False

    # Parse the comparison value
    if raw_value.lower() == "true":
        compare = True
    elif raw_value.lower() == "false":
        compare = False
    elif raw_value.lower() == "null" or raw_value.lower() == "none":
        compare = None
    else:
        try:
            compare = int(raw_value)
        except ValueError:
            try:
                compare = float(raw_value)
            except ValueError:
                # Strip quotes if present
                compare = raw_value.strip("'\"")

    # Evaluate
    if found_op == "==":
        return actual == compare
    elif found_op == "!=":
        return actual != compare
    elif found_op == ">":
        try:
            return actual > compare
        except TypeError:
            return False
    elif found_op == "<":
        try:
            return actual < compare
        except TypeError:
            return False
    elif found_op == ">=":
        try:
            return actual >= compare
        except TypeError:
            return False
    elif found_op == "<=":
        try:
            return actual <= compare
        except TypeError:
            return False
    elif found_op == "contains":
        if isinstance(actual, str) and isinstance(compare, str):
            return compare in actual
        elif isinstance(actual, list):
            return compare in actual
        return False

    return False


def cmd_get(args):
    if not os.path.exists(args.file):
        print(f"Error: file '{args.file}' not found", file=sys.stderr)
        sys.exit(1)

    with open(args.file) as f:
        data = json.load(f)

    segments = parse_path(args.path)
    results = resolve_path(data, segments)

    if args.format == "json":
        values = [r[0] for r in results]
        if len(values) == 1:
            print(json.dumps(values[0], indent=2))
        else:
            print(json.dumps(values, indent=2))
    else:
        for val, parent, key in results:
            print(json.dumps(val, indent=2, default=str))


def cmd_set(args):
    if not os.path.exists(args.file):
        print(f"Error: file '{args.file}' not found", file=sys.stderr)
        sys.exit(1)

    with open(args.file) as f:
        data = json.load(f)

    # Parse the value
    value_str = args.value
    try:
        value = json.loads(value_str)
    except (json.JSONDecodeError, ValueError):
        value = value_str

    segments = parse_path(args.path)
    result = set_value_at_path(data, segments, value)

    output_file = args.output if args.output else args.file

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))

    # Always write back to file
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    if not args.output:
        print(f"Updated {args.file}", file=sys.stderr)
    else:
        print(f"Written to {output_file}", file=sys.stderr)


def cmd_keys(args):
    if not os.path.exists(args.file):
        print(f"Error: file '{args.file}' not found", file=sys.stderr)
        sys.exit(1)

    with open(args.file) as f:
        data = json.load(f)

    if args.path:
        segments = parse_path(args.path)
        results = resolve_path(data, segments)
        if not results:
            print("No match", file=sys.stderr)
            sys.exit(1)
        target = results[0][0]
    else:
        target = data

    if isinstance(target, dict):
        keys = list(target.keys())
    elif isinstance(target, list):
        keys = list(range(len(target)))
    else:
        keys = []

    if args.format == "json":
        print(json.dumps(keys, indent=2))
    else:
        for k in keys:
            print(k)


def cmd_filter(args):
    if not os.path.exists(args.file):
        print(f"Error: file '{args.file}' not found", file=sys.stderr)
        sys.exit(1)

    with open(args.file) as f:
        data = json.load(f)

    # Navigate to path if specified
    if args.path:
        segments = parse_path(args.path)
        results = resolve_path(data, segments)
        if not results:
            print("Error: path not found", file=sys.stderr)
            sys.exit(1)
        data = results[0][0]

    if not isinstance(data, list):
        print("Error: target must be an array to use filter", file=sys.stderr)
        sys.exit(1)

    filtered = [item for item in data if evaluate_filter(item, args.expression)]

    if args.format == "json":
        print(json.dumps(filtered, indent=2))
    else:
        for item in filtered:
            print(json.dumps(item, indent=2, default=str))


def cmd_count(args):
    if not os.path.exists(args.file):
        print(f"Error: file '{args.file}' not found", file=sys.stderr)
        sys.exit(1)

    with open(args.file) as f:
        data = json.load(f)

    if args.path:
        segments = parse_path(args.path)
        results = resolve_path(data, segments)
        if not results:
            target = []
        else:
            target = results[0][0]
    else:
        target = data

    if isinstance(target, list):
        count = len(target)
    elif isinstance(target, dict):
        count = len(target)
    else:
        count = 1

    if args.format == "json":
        print(json.dumps({"count": count}))
    else:
        print(count)


def main():
    parser = argparse.ArgumentParser(
        description="JSON_Path — Query and transform JSON with path expressions. Zero deps.",
        prog="json_path",
    )
    sub = parser.add_subparsers(dest="command", help="Subcommand")

    # get
    p_get = sub.add_parser("get", help="Extract value at path")
    p_get.add_argument("file", help="JSON file to read")
    p_get.add_argument("path", help="Path expression (dot notation, brackets, wildcards, ..recursive)")
    p_get.add_argument("--format", choices=["text", "json"], default="text")

    # set
    p_set = sub.add_parser("set", help="Set value at path")
    p_set.add_argument("file", help="JSON file to modify")
    p_set.add_argument("path", help="Path expression")
    p_set.add_argument("value", help="Value to set (JSON or string)")
    p_set.add_argument("--output", help="Output file (default: modify in place)")
    p_set.add_argument("--format", choices=["text", "json"], default="text")

    # keys
    p_keys = sub.add_parser("keys", help="List keys at path (or root)")
    p_keys.add_argument("file", help="JSON file to inspect")
    p_keys.add_argument("--path", help="Path to list keys from (default: root)")
    p_keys.add_argument("--format", choices=["text", "json"], default="text")

    # filter
    p_filter = sub.add_parser("filter", help="Filter array items by expression")
    p_filter.add_argument("file", help="JSON file with array")
    p_filter.add_argument("expression", help="Filter expression (e.g., 'age > 30', 'name == Alice')")
    p_filter.add_argument("--path", help="Path to the array (e.g., 'users')")
    p_filter.add_argument("--format", choices=["text", "json"], default="text")

    # count
    p_count = sub.add_parser("count", help="Count elements at path")
    p_count.add_argument("file", help="JSON file")
    p_count.add_argument("--path", help="Path to count elements at (default: root)")
    p_count.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "get":
        cmd_get(args)
    elif args.command == "set":
        cmd_set(args)
    elif args.command == "keys":
        cmd_keys(args)
    elif args.command == "filter":
        cmd_filter(args)
    elif args.command == "count":
        cmd_count(args)


if __name__ == "__main__":
    main()
