#!/usr/bin/env python3
"""
Local LLM client using llama.cpp
Optimized for Qwen2.5 mobile worker inference.
"""

import subprocess
import os
import time


class LocalLLM:

    def __init__(self, model_path=None):

        if model_path:
            self.model_path = os.path.expanduser(model_path)
        else:
            self.model_path = os.path.expanduser(
                "~/AIOperator/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
            )

        self.llama_path = self._find_llama()

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Model not found: {self.model_path}"
            )

        if not self.llama_path:
            raise FileNotFoundError(
                "Could not find llama-cli binary"
            )

        print(
            f"[LocalLLM] Model: {os.path.basename(self.model_path)}"
        )
        print(
            f"[LocalLLM] Binary: {self.llama_path}"
        )


    def _find_llama(self):

        possible = [
            "~/llama.cpp/build/bin/llama-cli",
            "~/llama.cpp/build/bin/main",
            "~/llama.cpp/main",
            "~/llama.cpp/llama-cli"
        ]

        for path in possible:
            expanded = os.path.expanduser(path)

            if os.path.isfile(expanded):
                return expanded

        return None


    def _extract_json(self, text):

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and end > start:
            return text[start:end + 1].strip()

        return text.strip()

    def ask(self, prompt, max_tokens=96):

        formatted = prompt

        cmd = [
            self.llama_path,
            "-m",
            self.model_path,
            "-p",
            formatted,
            "-n",
            str(max_tokens),
            "--temp",
            "0.2",
            "-t",
            "6",
            "--ctx-size",
            "1024",
            "--simple-io",
            "--single-turn"
        ]

        try:

            print(
                f"[LocalLLM] Generating ({max_tokens} tokens)..."
            )

            start = time.time()

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            elapsed = time.time() - start


            if result.returncode != 0:

                print("===== LLAMA ERROR =====")
                print(result.stderr)
                print("=======================")

                return f"[Error] Exit {result.returncode}"


            output = result.stdout.strip()

            output = self._extract_json(output)


            print(
                f"[LocalLLM] Generated in {elapsed:.1f}s"
            )

            return output


        except subprocess.TimeoutExpired:

            return "[Timeout]"


        except Exception as e:

            return f"[Exception] {str(e)}"



if __name__ == "__main__":

    print("Testing LocalLLM...")

    try:

        llm = LocalLLM()

        response = llm.ask(
            'Return only JSON: {"actions":[]}'
        )

        print(response)

    except Exception as e:

        print(f"Error: {e}")