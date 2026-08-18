class WorkerPromptBuilder:

    @staticmethod
    def build(state):

        filesystem = f"""
/ANDROID
|
├── device
|   ├── platform: {state.get('device')}
|   └── status: {state.get('status')}
|
├── goals
{WorkerPromptBuilder.tree_list(state.get('goals', []))}
|
├── memory
{WorkerPromptBuilder.tree_memory(state.get('memory', []))}
|
└── workspace
    └── ~/AIOperator
"""


        return f"""
You are an Android autonomous worker.

You operate like a filesystem-aware AI.

CURRENT SYSTEM MAP:

{filesystem}


AVAILABLE ACTIONS:

- list_dir
- read_file
- write_file
- run_command


RULES:

- Return ONLY valid JSON.
- Never explain.
- Never return markdown.
- Never return a list of strings.

FORMAT:

{{
 "actions": [
   {{
    "type":"action_name",
    "params":{{}}
   }}
 ]
}}

Choose actions based on the system map.
"""


    @staticmethod
    def tree_list(items):

        if not items:
            return "│   └── none"

        return "\n".join(
            f"│   ├── {x}"
            for x in items
        )


    @staticmethod
    def tree_memory(memory):

        if not memory:
            return "│   └── empty"

        lines=[]

        for item in memory[-5:]:
            lines.append(
                f"│   ├── {item}"
            )

        return "\n".join(lines)