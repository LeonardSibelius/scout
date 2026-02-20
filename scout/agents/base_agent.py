"""
Base Agent class for Scout Intelligence System.
Adapted from Engine Room AI legal-demo.
"""

import os
import anthropic
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class BaseAgent(ABC):
    """Base class for all Scout agents."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        self.model = "claude-sonnet-4-5-20250929"
        self.max_tokens = 4000

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return output."""
        pass

    def call_claude(self, messages: list, system_prompt: Optional[str] = None) -> str:
        """Make a call to Claude API."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt or self.get_system_prompt(),
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            self.log(f"Claude API error: {str(e)}")
            return f"Error: {str(e)}"

    def log(self, message: str):
        """Log agent activity."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{self.name}] {message}")
