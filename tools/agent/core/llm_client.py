import os
import json
import logging
import re
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

class AgentLLMClient:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")

    def generate_code_implementation(self, task_description, repo_context):
        """
        Takes a task description and context and returns code changes
        """
        logger.info(f"Generating implementation for task: {task_description[:50]}...")
        if not self.api_key:
            logger.warning("No LLM API key configured. Mocking implementation failure.")
            return None

        system_prompt = (
            "You are an autonomous AI software engineer. "
            "You will be given a task description and the current repository context. "
            "You must respond ONLY with the modified file paths and their completely new content, "
            "formatted strictly as a JSON object where the keys are relative file paths "
            "and the values are the complete file contents."
        )

        user_prompt = f"Task: {task_description}\n\nContext:\n{json.dumps(repo_context)[:2000]}"

        data = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result['choices'][0]['message']['content']

                # Try to parse JSON from the response
                # Often models wrap in markdown ```json
                match = re.search(r'```(?:json)?(.*?)```', content, re.DOTALL)
                if match:
                    content = match.group(1)

                return json.loads(content)
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return None
