import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from config import Settings


class LLMPromptExtractor:
    """Extract key object terms using a small LLM."""

    def __init__(self, model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"):
        """
        Initialize with a lightweight LLM.

        Model options (smallest to largest):
        - "Qwen/Qwen2.5-0.5B-Instruct" (~500MB, very fast)
        - "microsoft/Phi-3.5-mini-instruct" (~7.5GB, more accurate)
        - "google/gemma-2-2b-it" (~2GB)
        """
        print(f"Loading model: {model_name}...")

        # Determine device
        self.device = Settings.DEVICE
        print(f"Using device: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
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
            Extracted object term for SAM3
        """
        system_prompt = """You are a helpful assistant that extracts object names from commands.
Extract ONLY the main object being referenced. Return just the object name, nothing else.

Examples:
"Grab that apple for me" -> apple
"I want a water bottle" -> water bottle
"Find my red cup" -> red cup
"Pick up the book on the table" -> book
"Get me the remote control" -> remote control"""

        user_prompt = f'"{phrase}" ->'

        # Format for chat models
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Apply chat template and get text
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Tokenize the text
        inputs = self.tokenizer(
            text, return_tensors="pt", padding=True, truncation=True
        )

        # Move to device
        input_ids = inputs["input_ids"].to(self.device)
        attention_mask = inputs["attention_mask"].to(self.device)

        # Generate response
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=20,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        # Decode only the generated part
        generated_tokens = outputs[0][input_ids.shape[1] :]
        response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        extracted = response.strip().lower()

        # Clean up any extra text
        extracted = self._clean_output(extracted)

        return extracted if extracted else phrase.strip().lower()

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
