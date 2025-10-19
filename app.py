from flask import Flask, render_template, request, Response, stream_with_context, jsonify
from werkzeug.exceptions import BadRequest
import requests
from config import API_URL

app = Flask(__name__)

BOUNDS = {
    "max_tokens": (32, 1024),
    "temperature": (0.0, 2.0),
    "top_p": (0.0, 1.0),
    "top_k": (1, 200),
    "repeat_penalty": (0.5, 2.0),
}

DEFAULTS = {
    "max_tokens": 256,
    "temperature": 0.5,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "back_translate": True,
}

def _clamp(val, lo, hi):
    try:
        return max(lo, min(hi, val))
    except TypeError:
        # if val is not numeric, fall back to lower bound
        return lo

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/summarize")
def summarize():
    """
    Proxy the request to FastAPI /summarize and stream the response back to the browser.
    """
    try:
        payload = request.get_json(force=True, silent=False)
        if not isinstance(payload, dict):
            raise BadRequest("JSON body must be an object")

        # Safety defaults
        for k, v in DEFAULTS.items():
            payload.setdefault(k, v)

        # Clamp numeric params into sane ranges to avoid backend blow-ups
        payload["max_tokens"]     = _clamp(int(payload.get("max_tokens", DEFAULTS["max_tokens"])), *BOUNDS["max_tokens"])
        payload["temperature"]    = _clamp(float(payload.get("temperature", DEFAULTS["temperature"])), *BOUNDS["temperature"])
        payload["top_p"]          = _clamp(float(payload.get("top_p", DEFAULTS["top_p"])), *BOUNDS["top_p"])
        payload["top_k"]          = _clamp(int(payload.get("top_k", DEFAULTS["top_k"])), *BOUNDS["top_k"])
        payload["repeat_penalty"] = _clamp(float(payload.get("repeat_penalty", DEFAULTS["repeat_penalty"])), *BOUNDS["repeat_penalty"])
        payload["back_translate"] = bool(payload.get("back_translate", DEFAULTS["back_translate"]))

        # Optional: simple size guard for the text field
        text = payload.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Field 'text' must be a non-empty string"}), 400
        if len(text) > 20000:
            return jsonify({"error": "Text too long (limit ~20k chars for demo)"}), 413

        # Connect timeout finite; read timeout None to allow long streams
        upstream = requests.post(
            f"{API_URL}/summarize",
            json=payload,
            stream=True,
            timeout=(5, None),
            headers={"Accept": "text/plain; charset=utf-8"},
        )

        # If upstream failed, return its body as-is (not streamed)
        if not upstream.ok:
            content_type = upstream.headers.get("Content-Type", "text/plain; charset=utf-8")
            body = upstream.text  # safe for small error bodies
            try:
                upstream.close()
            finally:
                pass
            return Response(body, status=upstream.status_code, content_type=content_type)

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=1024):
                    if not chunk:
                        continue
                    yield chunk.decode("utf-8", errors="ignore")
            except GeneratorExit:
                # Client disconnected; stop cleanly
                return
            finally:
                upstream.close()

        content_type = upstream.headers.get("Content-Type", "text/plain; charset=utf-8")
        return Response(stream_with_context(generate()), status=upstream.status_code, content_type=content_type)

    except BadRequest as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # Avoid leaking internals; keep it simple for the UI
        return jsonify({"error": f"Proxy error: {e}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True, threaded=True)
