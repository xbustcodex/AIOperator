# core/agent.py

#from ai.prompt_builder import PromptBuilder
from ai.llm_client import LLMClient
from core.action_router import ActionRouter
from ai.worker_prompt_builder import WorkerPromptBuilder

class Agent:

    @staticmethod
    def run(user_input):

        print("AGENT TYPE:", type(user_input))
        print("AGENT DATA:", user_input)

        prompt = WorkerPromptBuilder.build(user_input)

        ai_response = LLMClient.ask(prompt)

        print("\n===== RAW MODEL OUTPUT =====")
        print(ai_response)
        print("============================\n")

        return ActionRouter.route(ai_response)