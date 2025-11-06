# models/action_planner.py
from openai import OpenAI
import json
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class ActionPlanner:
    """GPT-based action planning"""

    def __init__(self, system_prompt_path: str):
        self.client = OpenAI()
        self.system_prompt = self._load_system_prompt(system_prompt_path)
        self.chat_history = [{"role": "system", "content": self.system_prompt}]

        logger.info("ActionPlanner initialized with GPT")

    def _load_system_prompt(self, path: str) -> str:
        """Load system prompt from file"""
        with open(path, "r") as f:
            return f.read()

    def plan_actions(self, request: Dict) -> List:
        """
        Generate action plan from object detections

        Args:
            request: Dictionary containing object_name, lexeme, 2d_position, question

        Returns:
            List of actions (e.g., [["pick", [x, y]], ["place", [x, y]]])
        """
        question = json.dumps(request)
        logger.info(f"Planning actions for: {question}")

        response = self._ask_gpt(question)

        # Parse response
        try:
            action_plan = json.loads(self._extract_code_block(response))
            logger.info(f"Generated action plan: {action_plan}")
            return action_plan
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response: {e}")
            logger.error(f"Response was: {response}")
            raise

    def _ask_gpt(self, question: str) -> str:
        """Send question to GPT and get response"""
        self.chat_history.append({"role": "user", "content": question})

        completion = self.client.chat.completions.create(
            model="gpt-4",
            messages=self.chat_history,
        )

        response = completion.choices[0].message.content
        self.chat_history.append({"role": "assistant", "content": response})

        return response

    def _extract_code_block(self, text: str) -> str:
        """Extract code from markdown code blocks"""
        # Look for ```json or ```python blocks
        if "```" in text:
            parts = text.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # Odd indices are inside code blocks
                    # Remove language identifier
                    lines = part.strip().split("\n")
                    if lines[0] in ["json", "python"]:
                        return "\n".join(lines[1:])
                    return part.strip()

        return text.strip()
