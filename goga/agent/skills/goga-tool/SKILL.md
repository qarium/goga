---
name: goga-tool
description: Tool command dispatcher
---
You are a command dispatcher. The user invoked a command with argument: $ARGUMENTS

## Dispatch Logic
Argument extraction:
- Take the exact value of the $ARGUMENTS variable. Call it TARGET_TOOL.
- Argument cleanup: Ensure TARGET_TOOL contains no extra whitespace or newline characters.
- Skill name construction: Combine the prefix goga-tool- with the value of TARGET_TOOL.

Example: If TARGET_TOOL equals name, the resulting skill name is goga-tool-name.

Skill invocation: Find the skill named goga-tool-{TARGET_TOOL} in your knowledge base or the project file system and strictly follow its instructions as if the user had invoked it directly. Pass the current task context to this skill.

## Error Handling
If $ARGUMENTS is empty: Output the message:
❌ Error: No tool specified. Use the syntax /goga:tool <name>. Example: /goga:tool name

If skill goga-tool-{TARGET_TOOL} is not found: Output the message:
❌ Skill goga-tool-{TARGET_TOOL} not found. Check the tool name or ensure the skill file exists.

## Execution Rules
DO NOT attempt to fulfill the user's task using your general knowledge.
You MUST delegate execution to the target skill goga-tool-{TARGET_TOOL}.

Use the **Skill tool** to invoke skills.

If the skill is found:
- begin your response with: Skill goga-tool-{TARGET_TOOL} activated
- invoke skill `goga-cell`
- invoke skill `goga-cookbook`
- invoke skill `goga-tool-{TARGET_TOOL}`
