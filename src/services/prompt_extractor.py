import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

import logging

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from config import AudioStreamingPipelineConfig, Settings

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


class LLMPromptExtractor:
    """Extract key object terms using a small LLM."""

    def __init__(self, model_name: str):
        """Initialize with a lightweight LLM."""
        print(f"Loading model: {model_name}...")

        # Determine device
        self.device = Settings.DEVICE
        print(f"Using device: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, dtype=torch.float16
        )
        self.model.to(self.device)
        self.model.eval()
        print("Model loaded successfully")

    def extract_object(self, phrase: str) -> str:
        """
        Extract the main object/noun from a command phrase.

        Args:
            phrase: Natural language command

        Returns:
            Extracted object term for object recognition, or empty string if none found, or "end" if termination command
        """
        system_prompt = """You are a helpful assistant that extracts object names from commands.
Extract ONLY the main object being referenced. Return just the object name, nothing else.
If the command is asking to stop, end, kill, terminate, quit, or cancel, return "end".
If there are multiple objects, return only the LAST one mentioned.
If there is no clear object, return an empty string.
Examples:
"Grab that apple for me" -> apple
"I want a water bottle" -> water bottle
"Find my red cup" -> red cup
"Pick up the book on the table" -> book
"Get me the remote control" -> remote control
"First grab the apple, then get the banana" -> banana
"Stop the robot" -> end
"Kill the process" -> end
"End the session" -> end
"Terminate now" -> end
"What time is it?" -> """

        user_prompt = f'"{phrase}" ->'

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.tokenizer(
            text, return_tensors="pt", padding=True, truncation=True
        )

        input_ids = inputs["input_ids"].to(self.device)
        attention_mask = inputs["attention_mask"].to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=20,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        generated_tokens = outputs[0][input_ids.shape[1] :]
        response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        extracted = response.strip().lower()
        extracted = self._clean_output(extracted)

        # Hard-coded fallback for termination keywords in case the model misses them
        termination_keywords = {
            "stop",
            "kill",
            "end",
            "terminate",
            "quit",
            "cancel",
            "abort",
        }
        if extracted in termination_keywords or any(
            kw in phrase.lower().split() for kw in termination_keywords
        ):
            return AudioStreamingPipelineConfig.STOP_KEYWORD

        return extracted  # Returns "" if empty, which is falsy — no fallback to phrase

    def _clean_output(self, text: str) -> str:
        """Clean up the LLM output."""
        text = text.strip()
        text = text.strip("\"'")
        text = text.split("\n")[0]

        if "(" in text:
            text = text.split("(")[0].strip()

        # Remove any trailing punctuation or extra words
        if text.endswith("."):
            text = text[:-1]

        return text.strip()


# Usage
if __name__ == "__main__":
    extractor = LLMPromptExtractor("Qwen/Qwen2.5-0.5B-Instruct")

    test_phrases = [
        "Grab that apple for me",
        "I want a water bottle",
        "Find my red cup",
        "Pick up the book on the table",
        "Get me the remote control please",
        "Where is my phone",
    ]

    for phrase in test_phrases:
        result = extractor.extract_object(phrase)
        print(f'"{phrase}" -> {result}')
