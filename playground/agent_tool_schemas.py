"""M3: what the model sees. The three file tools, described as JSON schemas.

What it demonstrates: to the model, a tool is pure data in the standard OpenAI
tool format. These dicts go out with every request; the model never sees the
Python code in agent_tools.py, only the names, descriptions and schemas here.

The lesson from M2's null-timezone bug, applied: each schema must match its
Python signature exactly. An optional parameter is ["string", "null"] and
defaults to None in Python. A required parameter is "string", is listed in
"required", and has no default. tests/test_agent_tools.py enforces this.
"""

PATH_DESCRIPTION = "File path relative to the sandbox root, e.g. 'notes.md'."

LIST_FILES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List the files and folders in the sandbox (the only folder you can access). Use it to see what exists before reading or writing.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": ["string", "null"],
                    "description": "Folder to list, relative to the sandbox root, e.g. 'drafts'. Use null or leave it out for the sandbox root.",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}

READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a UTF-8 text file from the sandbox and return its contents. Long files are cut off after 4000 characters.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": PATH_DESCRIPTION}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}

WRITE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Create a text file in the sandbox, or replace an existing file's entire content. Calling this automatically asks the user to approve the write; if they deny it, nothing is written. To change a file, read it first, then write the complete new content.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": PATH_DESCRIPTION},
                "content": {
                    "type": "string",
                    "description": "The complete new content of the file. This replaces everything in it.",
                },
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
}

# The full "tools" list the agent loop sends with every request.
TOOL_SCHEMAS = [LIST_FILES_SCHEMA, READ_FILE_SCHEMA, WRITE_FILE_SCHEMA]
