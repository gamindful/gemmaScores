"""Talk to a local Ollama model. Standard library only, no new dependencies."""

import base64
import io
import json
import re
import urllib.error
import urllib.request

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:e4b"


class Unavailable(RuntimeError):
    pass


class Ollama:
    def __init__(self, model=DEFAULT_MODEL, host=DEFAULT_HOST, think=False,
                 timeout=300):
        self.host = host.rstrip("/")
        self.think = think
        self.timeout = timeout
        self.model = self.resolve(model)
        self.calls = 0
        self.seconds = 0.0

    # ----------------------------------------------------------- discovery

    def tags(self):
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=10) as r:
                return [m["name"] for m in json.loads(r.read()).get("models", [])]
        except (urllib.error.URLError, OSError) as exc:
            raise Unavailable(
                f"no Ollama at {self.host} ({exc}). Start it with `ollama serve`.")

    def resolve(self, wanted):
        """Accept a loosely written model name, e.g. Gemma4:e4b."""
        names = self.tags()
        if not names:
            raise Unavailable("Ollama is running but has no models pulled.")
        low = wanted.lower()
        for name in names:
            if name.lower() == low:
                return name
        for name in names:
            if name.lower().startswith(low) or low in name.lower():
                return name
        base = re.sub(r"[^a-z0-9]", "", low.split(":")[0])
        for name in names:
            if re.sub(r"[^a-z0-9]", "", name.lower().split(":")[0]) == base:
                return name
        raise Unavailable(
            f"model {wanted!r} not found. Available: {', '.join(names)}")

    # ------------------------------------------------------------- calling

    def ask(self, prompt, images=(), system=None, max_tokens=None, schema=None,
            think=None):
        """One question, one answer. Images are PIL images or PNG bytes.

        Thinking is budgeted separately: the reasoning and the answer share the
        token allowance, so a thinking model needs room for both or it returns
        its reasoning and no answer at all.
        """
        import time
        think = self.think if think is None else think
        if max_tokens is None:
            max_tokens = 1400 if think else 500
        message = {"role": "user", "content": prompt}
        if images:
            message["images"] = [self._encode(i) for i in images]
        messages = ([{"role": "system", "content": system}] if system else [])
        messages.append(message)
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": bool(think),
            "options": {"temperature": 0.0, "num_predict": max_tokens},
        }
        if schema is not None:
            body["format"] = schema
        req = urllib.request.Request(
            self.host + "/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                payload = json.loads(r.read())
        except (urllib.error.URLError, OSError) as exc:
            raise Unavailable(f"the model call failed: {exc}")
        self.calls += 1
        self.seconds += time.time() - start
        msg = payload.get("message", {})
        content = msg.get("content", "")
        thinking = msg.get("thinking") or ""
        if think and not content.strip():
            # it spent the whole budget reasoning; ask again plainly
            return self.ask(prompt, images, system, max_tokens=500,
                            schema=schema, think=False)
        return content, thinking

    @staticmethod
    def _encode(image):
        if isinstance(image, (bytes, bytearray)):
            return base64.b64encode(image).decode()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


def first_json(text):
    """Pull the first JSON object out of a reply, fences and chatter included."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?|```", "", text)
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None
    return None
