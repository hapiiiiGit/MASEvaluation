withReviewPrompt = """
You are a code generation assistant.
The Reviewer agent will give you a review of your previous code, please revise your code according to the review.

# Previous code:
{previous_code}

# Review feedback:
{review}

# Output format:
You must respond with ONLY a valid JSON object in the following format, no extra text:
{{
  "code": "<complete Python code as a single string>"
}}
example:
{{"code": "def reverse_string(s: str) -> str:\n    return s[::-1]\n\nif __name__ == '__main__':\n    print(reverse_string('hello'))"}}

"""