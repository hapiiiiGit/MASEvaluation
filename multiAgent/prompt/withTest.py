withTestPrompt ="""
You are a code generation assistant.
The Tester agent executed your previous code against unittest test cases and got the results below.
Fix the code so that ALL test cases pass.

# Previous code:
{previous_code}

# Test cases and execution result:
{test_cases}

The section above contains:
- "### Test Code": the exact unittest code that was run
- "### Execution Result": the real output ([PASSED] / [FAILED] / [TIMEOUT]) with error details

Focus on the failing assertions and tracebacks to understand what needs to change.

# Output format:
You must respond with ONLY a valid JSON object in the following format, no extra text:
{{
  "code": "<complete Python code as a single string>"
}}
example:
{{"code": "def reverse_string(s: str) -> str:\n    return s[::-1]\n\nif __name__ == '__main__':\n    print(reverse_string('hello'))"}}


"""