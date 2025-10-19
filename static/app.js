const $ = (id) => document.getElementById(id);

let currentController = null;
let streaming = false;

function payload() {
  return {
    text: $("text").value || "",
    back_translate: $("back_translate").checked,
    max_tokens: Number($("max_tokens").value || 256),
    temperature: Number($("temperature").value || 0.5),
    top_p: Number($("top_p").value || 0.9),
    top_k: Number($("top_k").value || 40),
    repeat_penalty: Number($("repeat_penalty").value || 1.1),
  };
}

function setUIState({ status = "Idle", running = false } = {}) {
  $("status-text").textContent = status;
  $("go").disabled = running;
  $("clear").disabled = running; // optional: lock Clear during streaming
}

function appendChunk(chunk) {
  const out = $("out");
  out.textContent += chunk;
  // Auto-scroll container to bottom
  const scroller = out.parentElement;
  scroller.scrollTop = scroller.scrollHeight;
}

async function streamSummarize() {
  if (streaming) return; // ignore accidental double clicks
  streaming = true;
  setUIState({ status: "Requesting summary...", running: true });

  const out = $("out");
  out.textContent = "";

  // Cancel any in-flight request
  if (currentController) currentController.abort();
  currentController = new AbortController();

  let res;
  try {
    res = await fetch("/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
      signal: currentController.signal,
    });
  } catch (e) {
    if (e.name === "AbortError") {
      setUIState({ status: "Cancelled", running: false });
      streaming = false;
      return;
    }
    setUIState({ status: "Network error", running: false });
    out.textContent = String(e);
    streaming = false;
    return;
  }

  if (!res.ok || !res.body) {
    setUIState({ status: "Request failed", running: false });
    out.textContent = await res.text();
    streaming = false;
    return;
  }

  setUIState({ status: "Streaming...", running: true });

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      buffer += chunk;

      appendChunk(chunk);

    }

    setUIState({ status: "Done", running: false });
  } catch (e) {
    if (e.name === "AbortError") {
      setUIState({ status: "Cancelled", running: false });
    } else {
      setUIState({ status: "Stream error", running: false });
      appendChunk("\n[Stream error] " + String(e));
    }
  } finally {
    streaming = false;
    currentController = null;
  }
}

// Run button
$("go").addEventListener("click", () => {
  streamSummarize().catch((e) => {
    setUIState({ status: "Error", running: false });
    $("out").textContent = String(e);
    streaming = false;
  });
});

// Clear button
$("clear").addEventListener("click", () => {
  if (streaming && currentController) {
    currentController.abort();
  }
  $("out").textContent = "";
  setUIState({ status: "Idle", running: false });
});

// Keyboard shortcut: Ctrl/Cmd + Enter to run
document.addEventListener("keydown", (e) => {
  const meta = e.ctrlKey || e.metaKey;
  if (meta && e.key === "Enter") {
    $("go").click();
  }
});
