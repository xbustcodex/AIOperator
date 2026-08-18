# ai/llm
"""
LLM Client - Local-only version for AIOperator
"""
import os
import sys
from typing import Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ai.local_llm import LocalLLM
    LOCAL_LLM_AVAILABLE = True
except ImportError:
    LOCAL_LLM_AVAILABLE = False
    print("[LLMClient] Warning: local_llm.py not found")

class LLMClient:
    def __init__(self, use_local: bool = True):
        """
        Initialize LLM client.
        
        Args:
            use_local: If True, use local LLM; otherwise try OpenAI
        """
        self.use_local = use_local
        self.openai_available = False
        self.local_llm = None
        
        # Check for OpenAI API key (fallback only)
        if os.environ.get("OPENAI_API_KEY") and not use_local:
            try:
                import openai
                openai.api_key = os.environ["OPENAI_API_KEY"]
                self.client = openai
                self.openai_available = True
                print("[LLMClient] OpenAI API available (fallback)")
            except ImportError:
                print("[LLMClient] OpenAI package not installed")
                self.openai_available = False
        else:
            print("[LLMClient] Using local LLM (preferred)")
        
        # Initialize local LLM (PRIMARY)
        if LOCAL_LLM_AVAILABLE:
            try:
                self.local_llm = LocalLLM()
                print("[LLMClient] Local LLM initialized successfully")
            except Exception as e:
                print(f"[LLMClient] Failed to initialize local LLM: {e}")
                self.local_llm = None
        else:
            print("[LLMClient] LOCAL_LLM module not available")
    
    @staticmethod
    def ask(prompt: str) -> str:
        """Static method for backward compatibility with your agent.py"""
        return get_client()._ask(prompt)
        
    
    def _ask(self, prompt: str, max_tokens: int = 96) -> str:
        """
        Send prompt to LLM and get response.
        
        Args:
            prompt: The user input
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLM response
        """
        # Try local LLM first (always preferred)
        if self.local_llm:
            try:
                return self.local_llm.ask(prompt, max_tokens=max_tokens)
            except Exception as e:
                print(f"[LLMClient] Local LLM error: {e}")
                # Fall through
        
        # Try OpenAI if available (fallback only)
        if self.openai_available and not self.use_local:
            try:
                import openai
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.7
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"[LLMClient] OpenAI error: {e}")
        
        # Ultimate fallback
        return f"""I'm your local AI assistant. You asked: "{prompt}"

Since I'm running locally on your Android device, I can help you with:
- File operations (create, edit, delete files/folders)
- Running shell commands
- Writing and executing code
- System tasks and automation

What would you like me to do?"""

# Singleton for easy import
_client_instance = None

def get_client() -> LLMClient:
    """Get or create LLM client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient(use_local=True)
    return _client_instance

# Backward compatibility function
def ask(prompt: str, **kwargs) -> str:
    """Convenience function to ask the LLM (used by agent.py)"""
    client = get_client()
    return client._ask(prompt, **kwargs)

if __name__ == "__main__":
    # Test the client
    print("🧪 Testing LLMClient...")
    response = ask("What is 2+2?")
    print(f"📝 Response: {response}")