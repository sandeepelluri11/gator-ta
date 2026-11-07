"""OpenAI function-calling schemas. Kept separate from the implementations so the prompt
layer can ship them to the model without importing YAML loading code."""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_office_hours",
            "description": "List office hours for the course staff, optionally filtered to one "
            "weekday. Use this for any question about when or where to get help in person.",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "Weekday name such as 'Monday'. Omit for all days.",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deadlines",
            "description": "List assignment, project and exam dates. Use this for any question "
            "about what is due and when.",
            "parameters": {
                "type": "object",
                "properties": {
                    "upcoming_only": {
                        "type": "boolean",
                        "description": "Only return items due on or after today.",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_grading_policy",
            "description": "Return the grade breakdown, late policy and collaboration policy.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]
