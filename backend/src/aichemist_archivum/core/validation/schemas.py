file_tree_schema = {
    "type": "object",
    "patternProperties": {".*": {"type": ["object", "null"]}},
}

code_summary_schema = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "args": {"type": "array", "items": {"type": "string"}},
                    "lineno": {"type": "integer"},
                },
                "required": ["type", "name", "lineno"],
            },
        }
    },
}
